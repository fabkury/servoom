"""
Divoom API client for interacting with Divoom Gallery endpoints.
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import requests

from .config import Config
from .const import ApiEndpoint, Server
from .pixel_bean import PixelBean, PixelBeanState
from .pixel_bean_decoder import PixelBeanDecoder


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def convert_epoch_to_local(epoch: int) -> str:
    """
    Convert Unix epoch timestamp to local datetime string.
    
    Args:
        epoch: Unix timestamp
        
    Returns:
        Formatted datetime string (YYYY-MM-DD HH:MM:SS)
    """
    return datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing or replacing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for Windows/Unix filesystems
    """
    # Replace invalid Windows filename characters: < > : " / \ | ? *
    # Also replace other problematic characters
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    
    # Limit filename length (leaving room for extension and gallery ID prefix)
    max_length = 200
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def safe_console_text(value: Any) -> str:
    """
    Convert arbitrary text into a form that can be safely printed to the current console.
    
    Args:
        value: Value to render as text.
    
    Returns:
        String compatible with the console encoding, with unencodable characters replaced.
    """
    if value is None:
        text = ""
    else:
        text = str(value)
    
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        # Fallback to UTF-8 transformations if the console encoding behaves unexpectedly.
        return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def append_timestamp(filename: str) -> str:
    """
    Append current timestamp to filename.
    
    Args:
        filename: Original filename with extension
        
    Returns:
        Filename with timestamp appended before extension
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name, file_extension = os.path.splitext(filename)
    return f"{file_name}_{timestamp}{file_extension}"


# ============================================================================
# DIVOOM API CLIENT
# ============================================================================

class DivoomClient:
    """Client for interacting with Divoom API."""
    
    HEADERS = {
        'User-Agent': 'Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)',
        'Content-Type': 'application/json'
    }
    
    def __init__(self, email: str, md5_password: str = None, password: str = None):
        """
        Initialize Divoom API client.
        
        Args:
            email: User email
            md5_password: MD5 hashed password (preferred)
            password: Plain password (will be hashed to MD5)
        """
        if not any([password, md5_password]):
            raise ValueError('Empty password!')
        
        # Get MD5 hash of password if plain password provided
        if password:
            md5_password = hashlib.md5(password.encode('utf-8')).hexdigest()
        
        self._email = email
        self._md5_password = md5_password
        self.token = None
        self.user_id = None
        self._request_timeout = Config.REQUEST_TIMEOUT
    
    def _full_url(self, path: str, server: Server = Server.API) -> str:
        """Generate full URL from path"""
        if not path.startswith('/'):
            path = '/' + path
        return f'https://{server.value}{path}'
    
    def _send_request(self, endpoint: str, payload: dict = None) -> dict:
        """
        Send request to API server.
        
        Args:
            endpoint: API endpoint path (e.g., '/UserLogin')
            payload: Request payload dictionary
            
        Returns:
            JSON response as dictionary
        """
        if payload is None:
            payload = {}
        
        # Add auth tokens for non-login endpoints
        if endpoint != ApiEndpoint.USER_LOGIN.value:
            if not self.token or not self.user_id:
                raise ValueError("Not logged in! Call login() first.")
            payload.update({
                'Token': self.token,
                'UserId': self.user_id,
            })
        
        full_url = self._full_url(endpoint, Server.API)
        resp = requests.post(
            full_url,
            headers=self.HEADERS,
            json=payload,
            timeout=self._request_timeout,
        )
        return resp.json()
    
    def login(self) -> bool:
        """
        Authenticate with Divoom API.
        
        Returns:
            True if login successful, False otherwise
        """
        payload = {
            'Email': self._email,
            'Password': self._md5_password,
        }
        
        try:
            resp_json = self._send_request(ApiEndpoint.USER_LOGIN.value, payload)
            self.user_id = resp_json['UserId']
            self.token = resp_json['Token']
            print("[OK] Successfully logged in to Divoom API")
            return True
        except Exception as e:
            print(f"[ERROR] Login failed: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in or not"""
        return self.token is not None and self.user_id is not None
    
    # ========================================================================
    # CORE ARTWORK OPERATIONS
    # ========================================================================
    
    def fetch_artwork_info(self, gallery_id: int) -> Dict:
        """
        Fetch artwork metadata by gallery ID.
        
        Args:
            gallery_id: ID of the gallery/artwork
            
        Returns:
            Dictionary with artwork metadata, or None if failed
            
        Raises:
            ValueError: If not logged in
        """
        if not self.is_logged_in():
            raise ValueError("Not logged in! Call login() first.")
        
        payload = {
            'GalleryId': gallery_id,
        }
        
        try:
            resp_json = self._send_request(ApiEndpoint.GET_GALLERY_INFO.value, payload)
            if resp_json.get('ReturnCode', 0) != 0:
                print(f"[ERROR] Failed to fetch artwork info: ReturnCode {resp_json.get('ReturnCode')}")
                return None
            
            # Add gallery ID since it might not be included in the response
            resp_json['GalleryId'] = gallery_id
            return resp_json
        except Exception as e:
            print(f"[ERROR] Failed to fetch artwork info: {e}")
            return None
    
    def download_art_by_id(self, gallery_id: int, output_dir: str = None) -> Tuple[PixelBean, str]:
        """
        Download artwork by gallery ID. Fetches metadata, creates PixelBean, and downloads the file.
        
        Args:
            gallery_id: ID of the gallery/artwork to download
            output_dir: Directory to save downloaded file (default: 'downloads')
            
        Returns:
            Tuple of (PixelBean object, path to downloaded file)
            
        Raises:
            ValueError: If gallery info cannot be fetched or file cannot be downloaded
        """
        # Fetch artwork metadata
        metadata = self.fetch_artwork_info(gallery_id)
        if not metadata:
            raise ValueError(f"Failed to fetch metadata for gallery ID {gallery_id}")
        
        # Create PixelBean from metadata
        pixel_bean = PixelBean(metadata=metadata)
        
        # Download the artwork
        file_path = self.download_art(pixel_bean, output_dir=output_dir)
        
        return pixel_bean, file_path
    
    def download_art(self, pixel_bean: PixelBean, output_dir: str = None) -> str:
        """
        Download artwork file for a PixelBean and update its state.
        
        Args:
            pixel_bean: PixelBean with metadata (state: METADATA_ONLY)
            output_dir: Directory to save downloaded file (default: 'downloads')
            
        Returns:
            Path to downloaded file
            
        Raises:
            ValueError: If PixelBean doesn't have required metadata or is already downloaded
        """
        if pixel_bean.state != PixelBeanState.METADATA_ONLY:
            raise ValueError(f"Cannot download: PixelBean state is {pixel_bean.state.value}, expected METADATA_ONLY")
        
        file_id = pixel_bean.file_id
        if not file_id:
            raise ValueError("PixelBean missing FileId in metadata")
        
        gallery_id = pixel_bean.gallery_id
        file_name = pixel_bean.file_name or f'art_{gallery_id}'
        
        # Set default output directory
        if output_dir is None:
            output_dir = 'downloads'
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct download URL
        file_url = f"https://{Server.FILE.value}/{file_id}"
        
        # Create safe filename
        sanitized_name = sanitize_filename(file_name)
        safe_filename = f"{gallery_id}_{sanitized_name}.dat"
        output_path = os.path.join(output_dir, safe_filename)
        
        try:
            # Download the file
            resp = requests.get(
                file_url,
                headers=self.HEADERS,
                stream=True,
                timeout=self._request_timeout
            )
            resp.raise_for_status()
            
            # Write binary content to file
            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Update PixelBean state
            pixel_bean.update_from_download(output_path)
            print(f"[OK] Downloaded: {safe_console_text(safe_filename)}")
            return output_path
            
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download file: {e}") from e
        except IOError as e:
            raise RuntimeError(f"Failed to save file: {e}") from e
    
    def decode_art(self, pixel_bean: PixelBean) -> PixelBean:
        """
        Decode a downloaded Divoom file and update PixelBean with animation data.
        
        Args:
            pixel_bean: PixelBean with downloaded file (state: DOWNLOADED)
            
        Returns:
            Updated PixelBean with decoded animation data (state: COMPLETE)
            
        Raises:
            ValueError: If PixelBean doesn't have a file path or is not in DOWNLOADED state
        """
        if pixel_bean.state != PixelBeanState.DOWNLOADED:
            raise ValueError(f"Cannot decode: PixelBean state is {pixel_bean.state.value}, expected DOWNLOADED. Please download the file first.")
        
        file_path = pixel_bean.file_path
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        try:
            # Decode the file
            decoded_bean = PixelBeanDecoder.decode_file(file_path)
            if decoded_bean is None:
                raise ValueError("Failed to decode file: unsupported format or corrupted file")
            
            # Update PixelBean with decoded data
            pixel_bean.update_from_decode(
                total_frames=decoded_bean.total_frames,
                speed=decoded_bean.speed,
                row_count=decoded_bean.row_count,
                column_count=decoded_bean.column_count,
                frames_data=decoded_bean.frames_data
            )
            
            print(f"[OK] Decoded: {safe_console_text(os.path.basename(file_path))}")
            return pixel_bean
            
        except Exception as e:
            raise RuntimeError(f"Failed to decode file: {e}") from e
    
    def export_artworks_to_csv(
        self,
        pixel_beans: List[PixelBean],
        base_filename: str = 'artworks',
        output_dir: str = None,
        include_tags: bool = True
    ) -> Dict[str, str]:
        """
        Export artwork metadata to CSV files.
        
        Args:
            pixel_beans: List of PixelBean objects to export
            base_filename: Base filename for CSV files
            output_dir: Output directory (default: Config.OUTPUT_DIR)
            include_tags: Whether to create a separate tags CSV file
            
        Returns:
            Dictionary mapping export type to file path:
            - 'artworks': Path to main artworks CSV
            - 'tags': Path to tags CSV (if include_tags=True)
        """
        if output_dir is None:
            output_dir = Config.OUTPUT_DIR
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Process artworks data
        processed_data = []
        for bean in pixel_beans:
            metadata = bean.metadata
            row = {}
            for key, mapped_name in Config.FIELD_MAPPINGS.items():
                if key in metadata:
                    value = metadata[key]
                    # Apply transformations
                    if key == "Date":
                        value = convert_epoch_to_local(value)
                    elif key == "FileSize":
                        value = str(value)
                    row[mapped_name] = value
            processed_data.append(row)
        
        df_arts = pd.DataFrame(processed_data)
        
        # Export main artworks CSV
        filename = append_timestamp(f'{base_filename}.csv')
        artworks_path = os.path.join(output_dir, filename)
        df_arts.to_csv(artworks_path, index=False)
        print(f"[OK] Exported artworks: {artworks_path}")
        
        result = {'artworks': artworks_path}
        
        # Export tags CSV if requested
        if include_tags:
            tags_data = []
            for bean in pixel_beans:
                metadata = bean.metadata
                gallery_id = metadata.get("GalleryId")
                file_name = metadata.get("FileName")
                tags = metadata.get("FileTagArray", [])
                
                for tag in tags:
                    tags_data.append({
                        "GalleryId": gallery_id,
                        "Art Name": file_name,
                        "Tag Name": tag
                    })
            
            if tags_data:
                df_tags = pd.DataFrame(tags_data)
                tags_filename = append_timestamp(f'{base_filename}_tags.csv')
                tags_path = os.path.join(output_dir, tags_filename)
                df_tags.to_csv(tags_path, index=False)
                print(f"[OK] Exported tags: {tags_path}")
                result['tags'] = tags_path
        
        return result
    
    # ========================================================================
    # FETCH METHODS (return Dict for backward compatibility)
    # ========================================================================
    
    def fetch_my_arts(self, batch_size: int = None) -> List[Dict]:
        """
        Fetch all uploaded arts from the user's gallery.
        
        Args:
            batch_size: Number of items to fetch per request (default from Config)
            
        Returns:
            List of art dictionaries
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print("Fetching uploaded arts...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                "Version": 99,
                "FileSize": Config.FILE_SIZE_FILTER,
                "RefreshIndex": 0,
                "FileSort": 0,
                'Token': self.token,
                'UserId': self.user_id
            }
            
            try:
                resp = requests.post(
                    Config.MY_ARTS_ENDPOINT,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                data = resp.json()
                arts = data.get('FileList', [])
                
                if not arts:
                    break
                    
                all_arts.extend(arts)
                print(f"  Retrieved arts {start_num}-{end_num}. Total collected: {len(all_arts)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_arts) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_arts = all_arts[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except requests.RequestException as e:
                print(f"Error fetching arts: {e}")
                break
                
        print(f"[OK] Fetched {len(all_arts)} arts total")
        return all_arts
    
    def fetch_my_arts_as_beans(self, batch_size: int = None) -> List[PixelBean]:
        """
        Fetch all uploaded arts from the user's gallery as PixelBean objects.
        
        Args:
            batch_size: Number of items to fetch per request (default from Config)
            
        Returns:
            List of PixelBean objects (metadata-only state)
        """
        arts_data = self.fetch_my_arts(batch_size=batch_size)
        return [PixelBean(metadata=art) for art in arts_data]
    
    def fetch_likes_for_art(self, gallery_id: int, batch_size: int = None) -> List[Dict]:
        """
        Fetch all users who liked a specific art.
        
        Args:
            gallery_id: ID of the gallery/art item
            batch_size: Number of items to fetch per request (default from Config)
            
        Returns:
            List of user dictionaries who liked the art
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_likes = []
        start_num = 1
        
        while True:
            for attempt in range(Config.MAX_RETRIES):
                try:
                    payload = {
                        "StartNum": start_num,
                        "EndNum": start_num + batch_size - 1,
                        "GalleryId": gallery_id,
                        'Token': self.token,
                        'UserId': self.user_id
                    }
                    
                    resp = requests.post(
                        Config.MY_LIKES_ENDPOINT,
                        headers=self.HEADERS,
                        json=payload,
                        timeout=self._request_timeout
                    )
                    data = resp.json()
                    user_list = data.get('UserList', [])
                    
                    if not user_list:
                        return all_likes
                        
                    all_likes.extend(user_list)
                    start_num += batch_size
                    break
                    
                except requests.RequestException as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        raise
                    time.sleep(Config.RETRY_DELAY)
                    
        return all_likes
    
    def fetch_someone_arts(self, target_user_id: int, batch_size: int = None, debug: bool = False, **kwargs) -> List[Dict]:
        """
        Fetch arts uploaded by a specific user using GetSomeoneListV3 endpoint.
        
        Args:
            target_user_id: ID of the user whose arts to fetch
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of art dictionaries from the target user
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print(f"Fetching arts for User ID: {target_user_id}...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                "Version": 99,
                "ShowAllFlag": 1,
                "SomeOneUserId": target_user_id,
                "FileSize": Config.FILE_SIZE_FILTER,
                "RefreshIndex": 0,
                "FileSort": 0,
                'Token': self.token,
                'UserId': self.user_id,
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key.startswith("_"):  # Skip special flags
                    continue
                if value is None:
                    payload.pop(key, None)
                else:
                    payload[key] = value
            
            # DEBUG: Verbose request/response logging
            if debug:
                print(f"\n  REQUEST:")
                print(f"  Endpoint: {Config.SOMEONE_LIST_ENDPOINT}")
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            try:
                resp = requests.post(
                    Config.SOMEONE_LIST_ENDPOINT,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                
                # Try to parse JSON response
                try:
                    data = resp.json()
                except ValueError as e:
                    print(f"\n  [ERROR] Failed to parse JSON response")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Headers: {dict(resp.headers)}")
                    print(f"  Response Body (first 500 chars): {resp.text[:500]}")
                    break
                
                # DEBUG: Verbose response logging
                if debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    if debug:
                        print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                    break
                
                arts = data.get('FileList', [])
                
                if not arts:
                    break
                    
                all_arts.extend(arts)
                print(f"  Retrieved arts {start_num}-{end_num}. Total collected: {len(all_arts)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_arts) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_arts = all_arts[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except requests.RequestException as e:
                print(f"[ERROR] Request failed: {e}")
                break
                
        print(f"[OK] Fetched {len(all_arts)} arts from User ID {target_user_id}")
        return all_arts
    
    def fetch_someone_arts_as_beans(self, target_user_id: int, batch_size: int = None, debug: bool = False, **kwargs) -> List[PixelBean]:
        """
        Fetch arts uploaded by a specific user as PixelBean objects.
        
        Args:
            target_user_id: ID of the user whose arts to fetch
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of PixelBean objects (metadata-only state)
        """
        arts_data = self.fetch_someone_arts(target_user_id, batch_size=batch_size, debug=debug, **kwargs)
        return [PixelBean(metadata=art) for art in arts_data]
    
    def download_someone_arts(self, target_user_id: int, output_dir: str = None, batch_size: int = None, debug: bool = False, **kwargs) -> List[str]:
        """
        Download all arts from a specific user.
        
        Args:
            target_user_id: ID of the user whose arts to download
            output_dir: Directory to save downloaded files (default: 'downloads/{user_id}')
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of downloaded file paths
        """
        # Set default output directory
        if output_dir is None:
            output_dir = os.path.join('downloads', str(target_user_id))
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Downloading arts for User ID: {target_user_id}...")
        print(f"Output directory: {output_dir}")
        
        # Fetch the arts list as PixelBeans
        beans = self.fetch_someone_arts_as_beans(target_user_id, batch_size=batch_size, debug=debug, **kwargs)
        
        if not beans:
            print("No arts to download")
            return []
        
        downloaded_files = []
        print(f"\nDownloading {len(beans)} files...")
        
        for i, bean in enumerate(beans, 1):
            try:
                file_path = self.download_art(bean, output_dir=output_dir)
                downloaded_files.append(file_path)
            except Exception as e:
                gallery_id = bean.gallery_id or i
                print(f"  [{i}/{len(beans)}] Failed to download {gallery_id}: {e}")
        
        print(f"\n[OK] Downloaded {len(downloaded_files)}/{len(beans)} files to: {output_dir}")
        return downloaded_files
    
    def download_my_arts(self, output_dir: str = None, batch_size: int = None) -> List[str]:
        """
        Download all arts from the current user's gallery.
        
        Args:
            output_dir: Directory to save downloaded files (default: 'downloads/my_arts')
            batch_size: Number of items to fetch per request (default from Config)
            
        Returns:
            List of downloaded file paths
        """
        # Set default output directory
        if output_dir is None:
            output_dir = os.path.join('downloads', 'my_arts')
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Downloading my arts...")
        print(f"Output directory: {output_dir}")
        
        # Fetch the arts list as PixelBeans
        beans = self.fetch_my_arts_as_beans(batch_size=batch_size)
        
        if not beans:
            print("No arts to download")
            return []
        
        downloaded_files = []
        print(f"\nDownloading {len(beans)} files...")
        
        for i, bean in enumerate(beans, 1):
            try:
                file_path = self.download_art(bean, output_dir=output_dir)
                downloaded_files.append(file_path)
            except Exception as e:
                gallery_id = bean.gallery_id or i
                print(f"  [{i}/{len(beans)}] Failed to download {gallery_id}: {e}")
        
        print(f"\n[OK] Downloaded {len(downloaded_files)}/{len(beans)} files to: {output_dir}")
        return downloaded_files
    
    # ========================================================================
    # ADDITIONAL FETCH METHODS (keeping existing API)
    # ========================================================================
    
    def fetch_someone_info(self, target_user_id: int, debug: bool = False, **kwargs) -> Dict:
        """Fetch information about a specific user using GetSomeoneInfoV2 endpoint."""
        print(f"Fetching info for User ID: {target_user_id}...")
        
        payload = {
            'Token': self.token,
            'UserId': self.user_id,
            'SomeOneUserId': target_user_id,
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        
        # DEBUG: Verbose request/response logging
        if debug:
            print(f"\n  REQUEST:")
            print(f"  Endpoint: {Config.SOMEONE_INFO_ENDPOINT}")
            print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        try:
            resp = requests.post(
                Config.SOMEONE_INFO_ENDPOINT,
                headers=self.HEADERS,
                json=payload,
                timeout=self._request_timeout
            )
            data = resp.json()
            
            # DEBUG: Verbose response logging
            if debug:
                print(f"\n  RESPONSE:")
                print(f"  Status Code: {resp.status_code}")
                print(f"  Response Data:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Check for success
            if data.get('ReturnCode') == 0:
                print(f"[OK] Retrieved user info for User ID {target_user_id}")
                return data
            else:
                if debug:
                    print(f"[ERROR] Server returned error code: {data.get('ReturnCode')}")
                return None
                
        except (requests.RequestException, ValueError) as e:
            print(f"[ERROR] Request failed: {e}")
            return None
    
    def fetch_tag_info(self, tag_name: str, debug: bool = False, **kwargs) -> Dict:
        """Fetch information about a specific tag using Tag/GetTagInfo endpoint."""
        print(f"Fetching info for tag: {tag_name}...")
        
        payload = {
            'Token': self.token,
            'UserId': self.user_id,
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        
        # DEBUG: Verbose request/response logging
        if debug:
            print(f"\n  REQUEST:")
            print(f"  Endpoint: {Config.TAG_INFO_ENDPOINT}")
            print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        try:
            resp = requests.post(
                Config.TAG_INFO_ENDPOINT,
                headers=self.HEADERS,
                json=payload,
                timeout=self._request_timeout
            )
            data = resp.json()
            
            # DEBUG: Verbose response logging
            if debug:
                print(f"\n  RESPONSE:")
                print(f"  Status Code: {resp.status_code}")
                print(f"  Response Data:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Check for success
            if data.get('ReturnCode') == 0:
                print(f"[OK] Retrieved tag info for: {tag_name}")
                return data
            else:
                if debug:
                    print(f"[ERROR] Server returned error code: {data.get('ReturnCode')}")
                return None
                
        except (requests.RequestException, ValueError) as e:
            print(f"[ERROR] Request failed: {e}")
            return None
    
    def fetch_tag_gallery(self, tag_name: str, batch_size: int = None, debug: bool = False, **kwargs) -> List[Dict]:
        """Fetch arts from a specific tag using Tag/GetTagGalleryListV3 endpoint."""
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print(f"Fetching arts for tag: {tag_name}...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                'Token': self.token,
                'UserId': self.user_id,
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if value is None:
                    payload.pop(key, None)
                else:
                    payload[key] = value
            
            # DEBUG: Verbose request/response logging
            if debug:
                print(f"\n  REQUEST:")
                print(f"  Endpoint: {Config.TAG_LIST_ENDPOINT}")
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            try:
                resp = requests.post(
                    Config.TAG_LIST_ENDPOINT,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                data = resp.json()
                
                # DEBUG: Verbose response logging
                if debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    if debug:
                        print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                    break
                
                arts = data.get('FileList', [])
                
                if not arts:
                    break
                    
                all_arts.extend(arts)
                print(f"  Retrieved arts {start_num}-{end_num}. Total collected: {len(all_arts)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_arts) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_arts = all_arts[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except (requests.RequestException, ValueError) as e:
                print(f"[ERROR] Request failed: {e}")
                break
                
        print(f"[OK] Fetched {len(all_arts)} arts from tag: {tag_name}")
        return all_arts
    
    def search_user(self, query: str, debug: bool = False, **kwargs) -> List[Dict]:
        """Search for users using SearchUser endpoint."""
        print(f"Searching for users: {query}...")
        
        payload = {
            'Token': self.token,
            'UserId': self.user_id,
            'Keywords': query,
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        
        # DEBUG: Verbose request/response logging
        if debug:
            print(f"\n  REQUEST:")
            print(f"  Endpoint: {Config.SEARCH_USER_ENDPOINT}")
            print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        try:
            resp = requests.post(
                Config.SEARCH_USER_ENDPOINT,
                headers=self.HEADERS,
                json=payload,
                timeout=self._request_timeout
            )
            data = resp.json()
            
            # DEBUG: Verbose response logging
            if debug:
                print(f"\n  RESPONSE:")
                print(f"  Status Code: {resp.status_code}")
                print(f"  Response Data:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Check for success
            if data.get('ReturnCode') == 0:
                users = data.get('UserList', [])
                print(f"[OK] Found {len(users)} users")
                return users
            else:
                if debug:
                    print(f"[ERROR] Server returned error code: {data.get('ReturnCode')}")
                return []
                
        except (requests.RequestException, ValueError) as e:
            print(f"[ERROR] Request failed: {e}")
            return []
    
    def search_tag(self, query: str, debug: bool = False, **kwargs) -> List[Dict]:
        """Search for tags using Tag/SearchTagMoreV2 endpoint."""
        print(f"Searching for tags: {query}...")
        
        payload = {
            'Token': self.token,
            'UserId': self.user_id,
            'Keywords': query,
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        
        # DEBUG: Verbose request/response logging
        if debug:
            print(f"\n  REQUEST:")
            print(f"  Endpoint: {Config.SEARCH_TAG_ENDPOINT}")
            print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        try:
            resp = requests.post(
                Config.SEARCH_TAG_ENDPOINT,
                headers=self.HEADERS,
                json=payload,
                timeout=self._request_timeout
            )
            data = resp.json()
            
            # DEBUG: Verbose response logging
            if debug:
                print(f"\n  RESPONSE:")
                print(f"  Status Code: {resp.status_code}")
                print(f"  Response Data:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Check for success
            if data.get('ReturnCode') == 0:
                tags = data.get('TagList', [])
                print(f"[OK] Found {len(tags)} tags")
                return tags
            else:
                if debug:
                    print(f"[ERROR] Server returned error code: {data.get('ReturnCode')}")
                return []
                
        except (requests.RequestException, ValueError) as e:
            print(f"[ERROR] Request failed: {e}")
            return []
    
    def search_gallery(self, query: str, batch_size: int = None, debug: bool = False, **kwargs) -> List[Dict]:
        """Search for arts in gallery using SearchGalleryV3 endpoint."""
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print(f"Searching gallery: {query}...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                'Keywords': query,
                'Token': self.token,
                'UserId': self.user_id,
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if value is None:
                    payload.pop(key, None)
                else:
                    payload[key] = value
            
            # DEBUG: Verbose request/response logging
            if debug:
                print(f"\n  REQUEST:")
                print(f"  Endpoint: {Config.SEARCH_GALLERY_ENDPOINT}")
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            try:
                resp = requests.post(
                    Config.SEARCH_GALLERY_ENDPOINT,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                data = resp.json()
                
                # DEBUG: Verbose response logging
                if debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    if debug:
                        print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                    break
                
                arts = data.get('FileList', [])
                
                if not arts:
                    break
                    
                all_arts.extend(arts)
                print(f"  Retrieved arts {start_num}-{end_num}. Total collected: {len(all_arts)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_arts) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_arts = all_arts[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except (requests.RequestException, ValueError) as e:
                print(f"[ERROR] Request failed: {e}")
                break
                
        print(f"[OK] Found {len(all_arts)} arts matching: {query}")
        return all_arts
    
    def fetch_report_gallery(self, batch_size: int = None, debug: bool = True, **kwargs) -> List[Dict]:
        """Fetch reported gallery items using Manager/GetReportGallery endpoint."""
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_reports = []
        start_num = 1
        
        print(f"Fetching reported gallery items...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                "Token": self.token,
                "UserId": self.user_id,
                "CountryISOCode": "GB",
                "Classify": 18,
                "Pass": 1,
                "Add": 1,
                "Type": 0,
                "IsAddNew": 1,
                "IsAddRecommend": 1,
                "Good": 1,
                "IsAddGood": 1,
                "FileSize": 16,
                "FileType": 5,
                "FileSort": 0,
                "ShowAllFlag": 1,
                "GalleryId": 4152005,
                "CoId": 2237731,
                "CommentId": 2237731,
                "GalleryList": [4152005],
                "MessageId": 2237663,
                "CommentId": 2237663,
                "Version": 19,
                "OperatorUserId": self.user_id,
                "Operation": "Add",
                "Value": 1,
                "Language": "en",
                "RefreshIndex": 0,
                "SomeOneUserId": self.user_id,
                "CustomUserId": self.user_id,
                "GroupId": "I2",
                "GroupName": "Feedback & Suggestion",
                "ChannelId": "busChannel",
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key.startswith("_"):  # Skip special flags
                    continue
                if value is None:
                    payload.pop(key, None)
                else:
                    payload[key] = value
            
            # DEBUG: Verbose request/response logging
            if debug:
                print(f"\n  REQUEST:")
                print(f"  Endpoint: {Config.MANAGER_GET_REPORT_GALLERY}")
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            try:
                resp = requests.post(
                    Config.MANAGER_GET_REPORT_GALLERY,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                
                # Try to parse JSON response
                try:
                    data = resp.json()
                except ValueError as e:
                    print(f"\n  [ERROR] Failed to parse JSON response")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Headers: {dict(resp.headers)}")
                    print(f"  Response Body (first 500 chars): {resp.text[:500]}")
                    break
                
                # DEBUG: Verbose response logging
                if debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                    break
                
                # Check various possible field names for the reports list
                reports = data.get('ReportList', data.get('FileList', data.get('GalleryList', [])))
                
                if not reports:
                    break
                    
                all_reports.extend(reports)
                print(f"  Retrieved reports {start_num}-{end_num}. Total collected: {len(all_reports)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_reports) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_reports = all_reports[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except requests.RequestException as e:
                print(f"[ERROR] Request failed: {e}")
                break
                
        print(f"[OK] Fetched {len(all_reports)} reported gallery items")
        return all_reports
    
    def fetch_category_files(self, category_id: int, batch_size: int = None, debug: bool = False, **kwargs) -> List[Dict]:
        """Fetch files from a specific category using GetCategoryFileListV2 endpoint."""
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_files = []
        start_num = 1
        
        print(f"Fetching files for Category ID: {category_id}...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                "Classify": category_id,
                "FileSize": Config.FILE_SIZE_FILTER,
                "FileType": 5,
                "FileSort": 0,
                "Version": 12,
                "RefreshIndex": 0,
                'Token': self.token,
                'UserId': self.user_id,
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key.startswith("_"):  # Skip special flags
                    continue
                if value is None:
                    payload.pop(key, None)
                else:
                    payload[key] = value
            
            # DEBUG: Verbose request/response logging
            if debug:
                print(f"\n  REQUEST:")
                print(f"  Endpoint: {Config.GET_CATEGORY_FILES_ENDPOINT}")
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            try:
                resp = requests.post(
                    Config.GET_CATEGORY_FILES_ENDPOINT,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                
                # Try to parse JSON response
                try:
                    data = resp.json()
                except ValueError as e:
                    print(f"\n  [ERROR] Failed to parse JSON response")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Headers: {dict(resp.headers)}")
                    print(f"  Response Body (first 500 chars): {resp.text[:500]}")
                    break
                
                # DEBUG: Verbose response logging
                if debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    if debug:
                        print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                    break
                
                # Check various possible field names for the files list
                files = data.get('FileList', data.get('CategoryFileList', []))
                
                if not files:
                    break
                    
                all_files.extend(files)
                print(f"  Retrieved files {start_num}-{end_num}. Total collected: {len(all_files)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_files) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_files = all_files[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except requests.RequestException as e:
                print(f"[ERROR] Request failed: {e}")
                break
                
        print(f"[OK] Fetched {len(all_files)} files from Category ID {category_id}")
        return all_files
    
    def debug_fetch(self, batch_size: int = None, debug: bool = True, **kwargs) -> List[Dict]:
        """Debug fetch method."""
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_data = []
        start_num = 1
        
        print(f"Debug fetching...")
        while True:
            end_num = start_num + batch_size - 1
            
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                'Token': self.token,
                'UserId': self.user_id,
                'GalleryId': 4152005,
                'MessageId': 2237663,
                'CommentId': 2237663,
                'CustomUserId': self.user_id,
                "GroupId": "I2",
                "GroupName": "Feedback & Suggestion",
                "ChannelId": "busChannel",
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key.startswith("_"):  # Skip special flags
                    continue
                if value is None:
                    payload.pop(key, None)
                else:
                    payload[key] = value
            
            # DEBUG: Verbose request/response logging
            if debug:
                print(f"\n  REQUEST:")
                print(f"  Endpoint: {Config.MANAGER_GET_REPORT_GALLERY}")
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            try:
                resp = requests.post(
                    Config.MANAGER_GET_REPORT_GALLERY,
                    headers=self.HEADERS,
                    json=payload,
                    timeout=self._request_timeout
                )
                
                # Try to parse JSON response
                try:
                    data = resp.json()
                except ValueError as e:
                    print(f"\n  [ERROR] Failed to parse JSON response")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Headers: {dict(resp.headers)}")
                    print(f"  Response Body (first 500 chars): {resp.text[:500]}")
                    break
                
                # DEBUG: Verbose response logging
                if debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                    break
                
                # Check various possible field names for the reports list
                reports = data.get('ReportList', data.get('FileList', data.get('GalleryList', [])))
                
                if not reports:
                    break
                    
                all_data.extend(reports)
                print(f"  Retrieved reports {start_num}-{end_num}. Total collected: {len(all_data)}")
                
                # Stop early if debug mode limit reached
                if Config.DEBUG_MODE and len(all_data) >= Config.DEBUG_LIMIT:
                    print(f"[DEBUG MODE] Reached limit of {Config.DEBUG_LIMIT} items, stopping fetch")
                    all_data = all_data[:Config.DEBUG_LIMIT]
                    break
                
                start_num += batch_size
                
            except requests.RequestException as e:
                print(f"[ERROR] Request failed: {e}")
                break
                
        print(f"[OK] Fetched {len(all_data)} reported gallery items")
        return all_data

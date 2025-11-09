"""
Divoom API client for interacting with Divoom Gallery endpoints.
"""

import json
import re
import time
from datetime import datetime
from typing import Dict, List

import requests

from .api_client import APIxoo
from .config import Config


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


# ============================================================================
# DIVOOM API CLIENT
# ============================================================================

class DivoomClient:
    """Client for interacting with Divoom API."""
    
    def __init__(self, email: str, md5_password: str):
        """
        Initialize Divoom API client.
        
        Args:
            email: User email
            md5_password: MD5 hashed password
        """
        self.api = APIxoo(email, md5_password=md5_password)
        self.token = None
        self.user_id = None
        
    def login(self) -> bool:
        """
        Authenticate with Divoom API.
        
        Returns:
            True if login successful, False otherwise
        """
        status = self.api.log_in()
        if status:
            self.token = self.api._user['token']
            self.user_id = self.api._user['user_id']
            print("[OK] Successfully logged in to Divoom API")
            return True
        else:
            print("[ERROR] Login failed!")
            return False

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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
                        headers=Config.HEADERS,
                        json=payload,
                        timeout=Config.REQUEST_TIMEOUT
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
            
        Note:
            Fill in the correct payload parameters for this endpoint.
            Use debug=True to see request/response details.
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print(f"Fetching arts for User ID: {target_user_id}...")
        while True:
            end_num = start_num + batch_size - 1
            
            # Payload for GetSomeoneListV2
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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
                
                # TODO: Verify the correct field name for the arts list
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
        import os
        from config import Config
        
        # Set default output directory
        if output_dir is None:
            output_dir = os.path.join('downloads', str(target_user_id))
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Downloading arts for User ID: {target_user_id}...")
        print(f"Output directory: {output_dir}")
        
        # Fetch the arts list
        arts_data = self.fetch_someone_arts(target_user_id, batch_size=batch_size, debug=debug, **kwargs)
        
        if not arts_data:
            print("No arts to download")
            return []
        
        downloaded_files = []
        print(f"\nDownloading {len(arts_data)} files...")
        
        for i, art in enumerate(arts_data, 1):
            file_id = art.get('FileId')
            file_name = art.get('FileName', f'art_{i}')
            gallery_id = art.get('GalleryId', i)
            
            if not file_id:
                print(f"  [{i}/{len(arts_data)}] Skipping art {gallery_id}: No FileId")
                continue
            
            # Construct download URL using the same pattern as apixoo
            file_url = f"https://f.divoom-gz.com/{file_id}"
            
            # Create safe filename using gallery ID and sanitized original filename
            sanitized_name = sanitize_filename(file_name)
            safe_filename = f"{gallery_id}_{sanitized_name}.dat"
            output_path = os.path.join(output_dir, safe_filename)
            
            try:
                # Download the file in binary format
                resp = requests.get(
                    file_url,
                    headers=Config.HEADERS,
                    stream=True,
                    timeout=Config.REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                
                # Write binary content to file
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                downloaded_files.append(output_path)
                print(f"  [{i}/{len(arts_data)}] Downloaded: {safe_filename}")
                
            except requests.RequestException as e:
                print(f"  [{i}/{len(arts_data)}] Failed to download {gallery_id}: {e}")
            except IOError as e:
                print(f"  [{i}/{len(arts_data)}] Failed to save {gallery_id}: {e}")
        
        print(f"\n[OK] Downloaded {len(downloaded_files)}/{len(arts_data)} files to: {output_dir}")
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
        import os
        from config import Config
        
        # Set default output directory
        if output_dir is None:
            output_dir = os.path.join('downloads', 'my_arts')
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Downloading my arts...")
        print(f"Output directory: {output_dir}")
        
        # Fetch the arts list
        arts_data = self.fetch_my_arts(batch_size=batch_size)
        
        if not arts_data:
            print("No arts to download")
            return []
        
        downloaded_files = []
        print(f"\nDownloading {len(arts_data)} files...")
        
        for i, art in enumerate(arts_data, 1):
            file_id = art.get('FileId')
            file_name = art.get('FileName', f'art_{i}')
            gallery_id = art.get('GalleryId', i)
            
            if not file_id:
                print(f"  [{i}/{len(arts_data)}] Skipping art {gallery_id}: No FileId")
                continue
            
            # Construct download URL using the same pattern as apixoo
            file_url = f"https://f.divoom-gz.com/{file_id}"
            
            # Create safe filename using gallery ID and sanitized original filename
            sanitized_name = sanitize_filename(file_name)
            safe_filename = f"{gallery_id}_{sanitized_name}.dat"
            output_path = os.path.join(output_dir, safe_filename)
            
            try:
                # Download the file in binary format
                resp = requests.get(
                    file_url,
                    headers=Config.HEADERS,
                    stream=True,
                    timeout=Config.REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                
                # Write binary content to file
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                downloaded_files.append(output_path)
                print(f"  [{i}/{len(arts_data)}] Downloaded: {safe_filename}")
                
            except requests.RequestException as e:
                print(f"  [{i}/{len(arts_data)}] Failed to download {gallery_id}: {e}")
            except IOError as e:
                print(f"  [{i}/{len(arts_data)}] Failed to save {gallery_id}: {e}")
        
        print(f"\n[OK] Downloaded {len(downloaded_files)}/{len(arts_data)} files to: {output_dir}")
        return downloaded_files
    
    def fetch_someone_info(self, target_user_id: int, debug: bool = False, **kwargs) -> Dict:
        """
        Fetch information about a specific user using GetSomeoneInfoV2 endpoint.
        
        Args:
            target_user_id: ID of the user whose info to fetch
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Dictionary with user information, or None if failed
            
        Note:
            Fill in the correct payload parameters for this endpoint.
            Use debug=True to see request/response details.
        """
        print(f"Fetching info for User ID: {target_user_id}...")
        
        # TODO: Configure the correct payload for GetSomeoneInfoV2
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
                headers=Config.HEADERS,
                json=payload,
                timeout=Config.REQUEST_TIMEOUT
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
        """
        Fetch information about a specific tag using Tag/GetTagInfo endpoint.
        
        Args:
            tag_name: Name of the tag to fetch info for
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Dictionary with tag information, or None if failed
            
        Note:
            Fill in the correct payload parameters for this endpoint.
            Use debug=True to see request/response details.
        """
        print(f"Fetching info for tag: {tag_name}...")
        
        # TODO: Configure the correct payload for Tag/GetTagInfo
        payload = {
            'Token': self.token,
            'UserId': self.user_id,
            # Add required parameters here
            # Example: 'TagName': tag_name,
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
                headers=Config.HEADERS,
                json=payload,
                timeout=Config.REQUEST_TIMEOUT
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
        """
        Fetch arts from a specific tag using Tag/GetTagGalleryListV3 endpoint.
        
        Args:
            tag_name: Name of the tag to fetch arts from
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of art dictionaries from the tag
            
        Note:
            Fill in the correct payload parameters for this endpoint.
            Use debug=True to see request/response details.
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print(f"Fetching arts for tag: {tag_name}...")
        while True:
            end_num = start_num + batch_size - 1
            
            # TODO: Configure the correct payload for Tag/GetTagGalleryListV3
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                # Add required parameters here
                # Example: 'TagName': tag_name,
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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
                
                # TODO: Verify the correct field name for the arts list
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
        """
        Search for users using SearchUser endpoint.
        
        Args:
            query: Search query string
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of user dictionaries matching the query
        """
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
                headers=Config.HEADERS,
                json=payload,
                timeout=Config.REQUEST_TIMEOUT
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
        """
        Search for tags using Tag/SearchTagMoreV2 endpoint.
        
        Args:
            query: Search query string
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of tag dictionaries matching the query
            
        Note:
            Fill in the correct payload parameters for this endpoint.
            Use debug=True to see request/response details.
        """
        print(f"Searching for tags: {query}...")
        
        # TODO: Configure the correct payload for Tag/SearchTagMoreV2
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
                headers=Config.HEADERS,
                json=payload,
                timeout=Config.REQUEST_TIMEOUT
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
        """
        Search for arts in gallery using SearchGalleryV3 endpoint.
        
        Args:
            query: Search query string
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of art dictionaries matching the query
            
        Note:
            Fill in the correct payload parameters for this endpoint.
            Use debug=True to see request/response details.
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_arts = []
        start_num = 1
        
        print(f"Searching gallery: {query}...")
        while True:
            end_num = start_num + batch_size - 1
            
            # TODO: Configure the correct payload for SearchGalleryV3
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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
                
                # TODO: Verify the correct field name for the arts list
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
        """
        Fetch reported gallery items using Manager/GetReportGallery endpoint.
        
        Args:
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of reported gallery dictionaries
            
        Note:
            This endpoint is used to retrieve gallery items that have been reported.
            Use debug=True to see request/response details.
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_reports = []
        start_num = 1
        
        print(f"Fetching reported gallery items...")
        while True:
            end_num = start_num + batch_size - 1
            
            # CLOUD_GALLERY_SELF(0),
            # CLOUD_GALLERY_DIVOOM(1),
            # CLOUD_GALLERY_HOT(2),
            # CLOUD_GALLERY_NEW(3);

            dimension = 16
            file_type = 5
            sort = 0

            # Payload for Manager/GetReportGallery
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
                "Classify": 18,
                "FileSize": dimension,
                "FileType": file_type,
                "FileSort": sort,
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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
                if 1 or debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    # if debug:
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
        """
        Fetch files from a specific category using GetCategoryFileListV2 endpoint.
        
        Args:
            category_id: ID of the category to fetch files from
            batch_size: Number of items to fetch per request (default from Config)
            debug: Enable verbose debugging output (default False)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of file dictionaries from the category
            
        Note:
            This endpoint is used to retrieve files from a specific category.
            Use debug=True to see request/response details.
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_files = []
        start_num = 1
        
        print(f"Fetching files for Category ID: {category_id}...")
        while True:
            end_num = start_num + batch_size - 1
            
            dimension = Config.FILE_SIZE_FILTER
            file_type = 5
            sort = 0

            # Payload for GetCategoryFileListV2
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                "Classify": category_id,
                "FileSize": dimension,
                "FileType": file_type,
                "FileSort": sort,
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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
        
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
            
        all_data = []
        start_num = 1
        
        print(f"Debug fetching...")
        while True:
            end_num = start_num + batch_size - 1
            
            # CLOUD_GALLERY_SELF(0),
            # CLOUD_GALLERY_DIVOOM(1),
            # CLOUD_GALLERY_HOT(2),
            # CLOUD_GALLERY_NEW(3);

            dimension = 16
            file_type = 5
            sort = 0

            # Payload
            payload = {
                "StartNum": start_num,
                "EndNum": end_num,
                'Token': self.token,
                'UserId': self.user_id,
                # 'CountryISOCode': 'GB',
                # 'Classify': 18,
                # 'Pass': 1,
                # 'Add': 1,
                # 'Type': 0,
                # 'IsAddNew': 1,
                # 'IsAddRecommend': 1,
                # 'Good': 1,
                # 'IsAddGood': 1,
                # 'Classify': 18,
                # 'FileSize': dimension,
                # 'FileType': file_type,
                # 'FileSort': sort,
                # 'ShowAllFlag': 1,
                'GalleryId': 4152005,
                # 'CoId': 2237731,
                # 'CommentId': 2237731,
                # 'GalleryList': [4152005],
                'MessageId': 2237663,
                'CommentId': 2237663,
                # 'Version': 19,
                # 'OperatorUserId': self.user_id,
                # 'Operation': 'Add',
                # # 'Value': 1,
                # 'Language': 'en',
                # 'RefreshIndex': 0,
                # 'SomeOneUserId': self.user_id,
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
                    headers=Config.HEADERS,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
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
                if 1 or debug:
                    print(f"\n  RESPONSE:")
                    print(f"  Status Code: {resp.status_code}")
                    print(f"  Response Data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Check for errors
                if data.get('ReturnCode', 0) != 0:
                    # if debug:
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
    

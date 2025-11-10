"""
Divoom Data Fetcher
Retrieves data from Divoom API.

Supported DAT File Formats:
- ✓ Format 9 (0x09): 16x16 single animation
- ✓ Format 17 (0x11): Multiple picture format
- ✓ Format 18 (0x12): 32x32 or 64x64 animation
- ✓ Format 26 (0x1A): 64x64 or 128x128 animation
- ✓ Format 31 (0x1F): 128x128 embedded JPEG animation
- x Format 41: TODO
- ✓ Format 42 (0x2A): 256x256 zstd-compressed raw RGB frames
- ✓ Format 43 (0x2B): 256x256 embedded GIF/WEBP container
"""

import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Union

# Add parent directory to path to allow running as script
if __package__ is None:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

import numpy as np
import pandas as pd
from tqdm import tqdm

try:
    from .client import DivoomClient, convert_epoch_to_local
    from .config import Config
    from .pixel_bean_decoder import PixelBeanDecoder
except ImportError:
    # Allow running as a script directly
    from servoom.client import DivoomClient, convert_epoch_to_local
    from servoom.config import Config
    from servoom.pixel_bean_decoder import PixelBeanDecoder


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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
# DATA PROCESSORS
# ============================================================================

class DataProcessor:
    """Processes raw API data into structured formats."""
    
    @staticmethod
    def process_arts(arts_data: List[Dict]) -> pd.DataFrame:
        """
        Process arts data into a structured DataFrame.
        
        Args:
            arts_data: Raw arts data from API
            
        Returns:
            Processed DataFrame with mapped columns
        """
        print("\nProcessing arts data...")
        
        # Check for unmapped columns
        if arts_data:
            all_columns = set(arts_data[0].keys())
            mapped_columns = set(Config.FIELD_MAPPINGS.keys())
            ignored_columns = all_columns - mapped_columns
            
            if ignored_columns:
                print("Columns not mapped (will be ignored):")
                for col in sorted(ignored_columns):
                    print(f"  - {col}")
        
        # Transform data with field mappings
        processed_data = []
        for art in arts_data:
            row = {}
            for key, mapped_name in Config.FIELD_MAPPINGS.items():
                if key in art:
                    value = art[key]
                    # Apply transformations
                    if key == "Date":
                        value = convert_epoch_to_local(value)
                    elif key == "FileSize":
                        value = str(value)
                    row[mapped_name] = value
            processed_data.append(row)
            
        df = pd.DataFrame(processed_data)
        print(f"[OK] Processed {len(df)} arts")
        return df
    
    @staticmethod
    def extract_tags(arts_data: List[Dict]) -> pd.DataFrame:
        """
        Extract tags from arts data into a separate table.
        
        Args:
            arts_data: Raw arts data from API
            
        Returns:
            DataFrame with art-tag relationships
        """
        print("\nExtracting tags...")
        
        tags_data = []
        for art in arts_data:
            gallery_id = art.get("GalleryId")
            file_name = art.get("FileName")
            tags = art.get("FileTagArray", [])
            
            for tag in tags:
                tags_data.append({
                    "GalleryId": gallery_id,
                    "Art Name": file_name,
                    "Tag Name": tag
                })
        
        df = pd.DataFrame(tags_data)
        print(f"[OK] Extracted {len(df)} tag relationships")
        return df
    
    @staticmethod
    def process_likes(likes_data: List[Dict], gallery_id: int) -> List[Dict]:
        """
        Process likes data for a specific art.
        
        Args:
            likes_data: Raw likes data from API
            gallery_id: ID of the gallery/art
            
        Returns:
            List of processed like dictionaries
        """
        processed_likes = []
        for user in likes_data:
            processed_likes.append({
                "GalleryId": gallery_id,
                "NickName": user.get("NickName"),
                "UserId": user.get("UserId"),
                "Fans": user.get("FansCnt"),
                "Score": user.get("Score"),
                "Level": user.get("Level"),
                "Region": user.get("RegionId"),
                "Follower": "Yes" if user.get("IsFollow") == 1 else "No"
            })
        return processed_likes


# ============================================================================
# DATA EXPORTER
# ============================================================================

class DataExporter:
    """Handles exporting data to CSV files."""
    
    @staticmethod
    def export_to_csv(df: pd.DataFrame, base_filename: str, output_dir: str = None) -> str:
        """
        Export DataFrame to CSV with timestamp.
        
        Args:
            df: DataFrame to export
            base_filename: Base filename (timestamp will be appended)
            output_dir: Output directory (default: Config.OUTPUT_DIR)
            
        Returns:
            Full path of exported file
        """
        if output_dir is None:
            output_dir = Config.OUTPUT_DIR
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp
        filename = append_timestamp(base_filename)
        filepath = os.path.join(output_dir, filename)
        
        # Export to CSV
        df.to_csv(filepath, index=False)
        print(f"[OK] Exported: {filepath}")
        return filepath


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class DivoomDataFetcher:
    """Main application orchestrator."""
    
    def __init__(self):
        """Initialize the data fetcher."""
        self.client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
        self.processor = DataProcessor()
        self.exporter = DataExporter()
        
    def run(self):
        """Execute the full data fetching and processing pipeline."""
        print("=" * 70)
        print("Divoom Gallery Data Fetcher")
        print("=" * 70)
        
        # Display debug mode warning
        if Config.DEBUG_MODE:
            print(f"\n[!] DEBUG MODE: Processing limited to {Config.DEBUG_LIMIT} arts\n")
        
        # Step 1: Login
        if not self.client.login():
            return
        
        # Step 2: Fetch arts
        print("\n" + "-" * 70)
        arts_data = self.client.fetch_my_arts()
        if not arts_data:
            print("No arts found.")
            return

        # return
        
        # Step 3: Process and export arts
        print("\n" + "-" * 70)
        df_arts = self.processor.process_arts(arts_data)
        self.exporter.export_to_csv(df_arts, 'main_table.csv')
        
        # Step 4: Extract and export tags
        print("\n" + "-" * 70)
        df_tags = self.processor.extract_tags(arts_data)
        self.exporter.export_to_csv(df_tags, 'tags_table.csv')
        
        # Step 5: Fetch likes for each art
        print("\n" + "-" * 70)
        print("Fetching likes for each art...")
        all_likes = []
        total_likes_count = 0
        next_report_threshold = Config.LIKES_REPORT_INTERVAL
        
        for _, row in tqdm(df_arts.iterrows(), total=len(df_arts), desc="Processing arts"):
            gallery_id = row["Gallery ID"]
            try:
                likes_data = self.client.fetch_likes_for_art(gallery_id)
                processed_likes = self.processor.process_likes(likes_data, gallery_id)
                all_likes.extend(processed_likes)
                
                total_likes_count += len(processed_likes)
                if total_likes_count >= next_report_threshold:
                    tqdm.write(f"Total likes processed: {total_likes_count}")
                    next_report_threshold += Config.LIKES_REPORT_INTERVAL
                    
            except Exception as e:
                tqdm.write(f"Failed to fetch likes for Gallery ID {gallery_id}: {e}")
        
        # Step 6: Export likes
        print("\n" + "-" * 70)
        df_likes = pd.DataFrame(all_likes)
        self.exporter.export_to_csv(df_likes, 'all_arts_likes.csv')
        
        # Summary
        print("\n" + "=" * 70)
        print("Summary:")
        print(f"  - Arts exported: {len(df_arts)}")
        print(f"  - Tags exported: {len(df_tags)}")
        print(f"  - Likes exported: {len(df_likes)}")
        print("=" * 70)
        print("[SUCCESS] All data successfully exported!")


# ============================================================================
# DEBUG/TEST FUNCTIONS
# ============================================================================
# These functions are kept for debugging API endpoints.
# Enable debug mode in the methods to see detailed request/response info.

def test_fetch_my_arts(export_csv: bool = True, debug: bool = False, **kwargs):
    """
    Test function to fetch my own arts with debugging enabled.
    
    Args:
        export_csv: Whether to export results to CSV (default True)
        debug: Enable verbose debugging output (default False)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        List of art dictionaries or None if failed
    """
    print("=" * 70)
    print("Testing GetMyUploadListV3 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return None
    
    print("\n" + "-" * 70)
    print("Fetching my arts...")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    try:
        arts_data = client.fetch_my_arts(**kwargs)
        
        if not arts_data:
            print("[INFO] No arts returned")
            return None
        
        print(f"\n[SUCCESS] Retrieved {len(arts_data)} arts!")
        
        # Show sample structure
        if arts_data:
            print("\nSample art structure (first item):")
            sample = arts_data[0]
            for key, value in sample.items():
                value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"  {key}: {value_preview}")
        
        # Export to CSV if requested
        if export_csv:
            print("\n" + "-" * 70)
            df = pd.DataFrame(arts_data)
            exporter = DataExporter()
            filename = exporter.export_to_csv(df, 'my_arts.csv')
            print(f"Data exported to: {filename}")
        
        return arts_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fetch_someone_arts(target_user_id: int, export_csv: bool = True, debug: bool = True, **kwargs):
    """
    Test function to fetch another user's arts with debugging enabled.
    
    Args:
        target_user_id: ID of the user whose arts to fetch
        export_csv: Whether to export results to CSV (default True)
        debug: Enable verbose debugging output (default True)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        List of art dictionaries or None if failed
    """
    print("=" * 70)
    print("Testing GetSomeoneListV3 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return None
    
    print("\n" + "-" * 70)
    print(f"Fetching arts for User ID: {target_user_id}")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    try:
        arts_data = client.fetch_someone_arts(target_user_id, debug=debug, **kwargs)
        
        if not arts_data:
            print("[INFO] No arts returned")
            return None
        
        print(f"\n[SUCCESS] Retrieved {len(arts_data)} arts!")
        
        # Show sample structure
        if arts_data:
            print("\nSample art structure (first item):")
            sample = arts_data[0]
            for key, value in sample.items():
                value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"  {key}: {value_preview}")
        
        # Export to CSV if requested
        if export_csv:
            print("\n" + "-" * 70)
            df = pd.DataFrame(arts_data)
            exporter = DataExporter()
            filename = exporter.export_to_csv(df, f'someone_arts_{target_user_id}.csv')
            print(f"Data exported to: {filename}")
        
        return arts_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fetch_someone_info(target_user_id: int, debug: bool = True, **kwargs):
    """
    Test function to fetch another user's info with debugging enabled.
    
    Args:
        target_user_id: ID of the user whose info to fetch
        debug: Enable verbose debugging output (default True)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        Dictionary with user information or None if failed
    """
    print("=" * 70)
    print("Testing GetSomeoneInfoV2 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return None
    
    print("\n" + "-" * 70)
    print(f"Fetching info for User ID: {target_user_id}")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    result = client.fetch_someone_info(target_user_id, debug=debug, **kwargs)
    
    if result and result.get('ReturnCode') == 0:
        print(f"\n[SUCCESS] Retrieved user info")
        return result
    else:
        print(f"\n[FAILED] Could not retrieve user info")
        return None


def test_search_user(query: str, debug: bool = True, **kwargs):
    """
    Test function to search for users with debugging enabled.
    
    Args:
        query: Search query string
        debug: Enable verbose debugging output (default True)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        List of user dictionaries or empty list if failed
    """
    print("=" * 70)
    print("Testing SearchUser Endpoint")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return []
    
    print("\n" + "-" * 70)
    print(f"Searching for users: {query}")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    results = client.search_user(query, debug=debug, **kwargs)
    
    if results:
        print(f"\n[SUCCESS] Found {len(results)} users")
        print("\nSample results:")
        for i, user in enumerate(results[:3]):  # Show first 3 results
            print(f"\n  User {i+1}:")
            for key, value in user.items():
                value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"    {key}: {value_preview}")
        return results
    else:
        print(f"\n[INFO] No users found")
        return []


def test_download_someone_arts(target_user_id: int, output_dir: str = None, debug: bool = False, **kwargs):
    """
    Test function to download someone's arts.
    
    Args:
        target_user_id: ID of the user whose arts to download
        output_dir: Directory to save downloaded files (default: 'downloads/{user_id}')
        debug: Enable verbose debugging output (default False)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        List of downloaded file paths
    """
    print("=" * 70)
    print("Testing Download Someone's Arts")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return []
    
    print("\n" + "-" * 70)
    
    try:
        downloaded_files = client.download_someone_arts(
            target_user_id, 
            output_dir=output_dir,
            debug=debug, 
            **kwargs
        )
        
        print(f"\n[SUCCESS] Downloaded {len(downloaded_files)} files")
        return downloaded_files
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_download_my_arts(output_dir: str = None):
    """
    Test function to download my arts.
    
    Args:
        output_dir: Directory to save downloaded files (default: 'downloads/my_arts')
    
    Returns:
        List of downloaded file paths
    """
    print("=" * 70)
    print("Testing Download My Arts")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return []
    
    print("\n" + "-" * 70)
    
    try:
        downloaded_files = client.download_my_arts(output_dir=output_dir)
        
        print(f"\n[SUCCESS] Downloaded {len(downloaded_files)} files")
        return downloaded_files
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_fetch_report_gallery(export_csv: bool = True, debug: bool = False, **kwargs):
    """
    Test function to fetch reported gallery items with debugging enabled.
    
    Args:
        export_csv: Whether to export results to CSV (default True)
        debug: Enable verbose debugging output (default True)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        List of reported gallery dictionaries or None if failed
    """
    print("=" * 70)
    print("Testing Manager/GetReportGallery Endpoint")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return None
    
    print("\n" + "-" * 70)
    print("Fetching reported gallery items...")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    try:
        reports_data = client.fetch_report_gallery(debug=debug, **kwargs)
        
        if not reports_data:
            print("[INFO] No reported gallery items returned")
            return None
        
        print(f"\n[SUCCESS] Retrieved {len(reports_data)} reported items!")
        
        # Show sample structure
        if reports_data:
            print("\nSample report structure (first item):")
            sample = reports_data[0]
            for key, value in sample.items():
                value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"  {key}: {value_preview}")
        
        # Export to CSV if requested
        if export_csv:
            print("\n" + "-" * 70)
            df = pd.DataFrame(reports_data)
            exporter = DataExporter()
            filename = exporter.export_to_csv(df, 'report_gallery.csv')
            print(f"Data exported to: {filename}")
        
        return reports_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fetch_category_files(category_id: int, export_csv: bool = False, debug: bool = True, **kwargs):
    """
    Test function to fetch files from a specific category with debugging enabled.
    
    Args:
        category_id: ID of the category to fetch files from
        export_csv: Whether to export results to CSV (default True)
        debug: Enable verbose debugging output (default True)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        List of file dictionaries or None if failed
    """
    print("=" * 70)
    print("Testing GetCategoryFileListV2 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return None
    
    print("\n" + "-" * 70)
    print(f"Fetching files for Category ID: {category_id}")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    try:
        files_data = client.fetch_category_files(category_id, debug=debug, **kwargs)
        
        if not files_data:
            print("[INFO] No files returned")
            return None
        
        print(f"\n[SUCCESS] Retrieved {len(files_data)} files!")
        
        # Show sample structure
        if files_data:
            print("\nSample file structure (first item):")
            sample = files_data[0]
            for key, value in sample.items():
                value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"  {key}: {value_preview}")
        
        # Export to CSV if requested
        if export_csv:
            print("\n" + "-" * 70)
            df = pd.DataFrame(files_data)
            exporter = DataExporter()
            filename = exporter.export_to_csv(df, f'category_{category_id}_files.csv')
            print(f"Data exported to: {filename}")
        
        return files_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_download_and_decode_gallery_files(category_id: int, output_dir: str = None, debug: bool = False, **kwargs):
    """
    Test function to fetch category files, download them, and decode them one by one.
    This is a combination of test_fetch_category_files() and test_download_and_decode_someone_arts().
    
    Args:
        category_id: ID of the category to fetch files from
        output_dir: Directory to save decoded WebP files (default: Config.OUTPUT_DIR)
        debug: Enable verbose debugging output (default False)
        **kwargs: Additional parameters to pass to the fetch API
    
    Returns:
        Tuple of (list of downloaded .dat paths, list of decoded .webp paths)
    """
    try:
        from .client import sanitize_filename
    except ImportError:
        from servoom.client import sanitize_filename
    import requests
    # Config already imported at top
    
    print("=" * 70)
    print("Testing Download and Decode Gallery Files from Category")
    print("=" * 70)
    
    # Step 1: Fetch category files
    client = DivoomClient(Config.EMAIL, Config.MD5_PASSWORD)
    if not client.login():
        return [], []
    
    print("\n" + "-" * 70)
    print(f"Fetching files for Category ID: {category_id}")
    if kwargs:
        print(f"Additional parameters: {kwargs}")
    
    try:
        files_data = client.fetch_category_files(category_id, debug=debug, **kwargs)
        
        if not files_data:
            print("[INFO] No files returned")
            return [], []
        
        print(f"\n[SUCCESS] Retrieved {len(files_data)} files!")
    except Exception as e:
        print(f"\n[ERROR] Failed to fetch category files: {e}")
        import traceback
        traceback.print_exc()
        return [], []
    
    # Step 2: Download the files
    # Use a separate directory for downloaded .dat files
    dat_output_dir = os.path.join('downloads', f'category-{category_id}', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(dat_output_dir, exist_ok=True)
    
    print("\n" + "-" * 70)
    print(f"Downloading {len(files_data)} files...")
    downloaded_files = []
    
    for i, file_info in enumerate(files_data, 1):
        file_id = file_info.get('FileId')
        file_name = file_info.get('FileName', f'file_{i}')
        gallery_id = file_info.get('GalleryId', file_info.get('FileId', i))
        
        if not file_id:
            print(f"  [{i}/{len(files_data)}] Skipping file {gallery_id}: No FileId")
            continue
        
        # Construct download URL using the same pattern as other download functions
        file_url = f"https://f.divoom-gz.com/{file_id}"
        
        # Create safe filename using gallery ID and sanitized original filename
        sanitized_name = sanitize_filename(file_name)
        safe_filename = f"{gallery_id}_{sanitized_name}.dat"
        output_path = os.path.join(dat_output_dir, safe_filename)
        
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
            print(f"  [{i}/{len(files_data)}] Downloaded: {safe_filename}")
            
        except requests.RequestException as e:
            print(f"  [{i}/{len(files_data)}] Failed to download {gallery_id}: {e}")
        except IOError as e:
            print(f"  [{i}/{len(files_data)}] Failed to save {gallery_id}: {e}")
    
    if not downloaded_files:
        print("\n[INFO] No files downloaded, nothing to decode")
        return [], []
    
    print(f"\n[OK] Downloaded {len(downloaded_files)}/{len(files_data)} files")
    
    # Step 3: Decode the downloaded files with proper naming
    if output_dir is None:
        decode_output_dir = Config.OUTPUT_DIR
    else:
        decode_output_dir = output_dir

    decode_output_dir += f'/category-{category_id}/' + datetime.now().strftime('%Y-%m-%d')
    
    os.makedirs(decode_output_dir, exist_ok=True)
    
    print("\n" + "-" * 70)
    print("Decoding downloaded DAT files to lossless WebP...")
    decoded_files = []
    
    for i, dat_path in enumerate(downloaded_files, 1):
        # Parse the filename: {gallery_id}_{artwork_name}.dat
        base_name = os.path.splitext(os.path.basename(dat_path))[0]
        
        try:
            # Split on first underscore to get gallery_id and artwork_name
            parts = base_name.split('_', 1)
            if len(parts) >= 2:
                gallery_id = parts[0]
                artwork_name = parts[1]
                
                # Sanitize the artwork name thoroughly
                # Remove or replace invalid characters
                safe_artwork_name = sanitize_filename(artwork_name)
                
                # Remove any remaining non-ASCII characters for safety
                safe_artwork_name = safe_artwork_name.encode('ascii', 'ignore').decode('ascii')
                
                # Remove multiple underscores/spaces
                safe_artwork_name = re.sub(r'[_\s]+', '_', safe_artwork_name)
                
                # Trim to reasonable length (leaving room for gallery_id and extension)
                max_name_length = 150
                if len(safe_artwork_name) > max_name_length:
                    safe_artwork_name = safe_artwork_name[:max_name_length]
                
                # Construct output filename: {gallery_id}_{safe_artwork_name}
                output_filename = f"{gallery_id}_{safe_artwork_name}"
                
                print(f"  [{i}/{len(downloaded_files)}] {gallery_id}: {safe_artwork_name}")
            else:
                # Fallback: just use gallery_id
                gallery_id = parts[0]
                output_filename = gallery_id
                print(f"  [{i}/{len(downloaded_files)}] {gallery_id}")
        except Exception as e:
            # Fallback: use the full base_name
            output_filename = sanitize_filename(base_name)
            print(f"  [{i}/{len(downloaded_files)}] Processing...")
        
        # Decode with custom output filename
        out_path = decode_dat_file(
            dat_path,
            output_dir=decode_output_dir,
            output_filename=output_filename
        )
        
        if out_path:
            decoded_files.append(out_path)
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Downloaded {len(downloaded_files)} files, decoded {len(decoded_files)} files")
    print("=" * 70)
    
    return downloaded_files, decoded_files


# ============================================================================
# DAT DECODING UTILITIES
# ============================================================================

def decode_dat_file(
    dat_path: str,
    output_dir: str = None,
    output_filename: str = None,
    scale: Union[int, float] = 1,
    target_width: int = None,
    target_height: int = None,
) -> str:
    """
    Decode a single .dat pixel animation into a lossless WebP animation.

    Args:
        dat_path: Path to the .dat file downloaded from Divoom
        output_dir: Directory to place the .webp (default: Config.OUTPUT_DIR)
        output_filename: Optional custom output filename (without extension)
        scale: Optional scale factor for output image
        target_width: Optional explicit width
        target_height: Optional explicit height

    Returns:
        Path to the generated .webp file, or empty string on failure
    """
    try:
        if output_dir is None:
            output_dir = Config.OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        # Determine output filename
        if output_filename:
            # Use provided filename
            safe_base_name = output_filename
        else:
            # Extract base name and sanitize for output (keep only ASCII-safe characters)
            base_name = os.path.splitext(os.path.basename(dat_path))[0]
            # Keep only the file ID (before first underscore) to avoid Unicode issues
            try:
                file_id = base_name.split('_')[0]
                safe_base_name = file_id
            except:
                safe_base_name = base_name
        
        out_path = os.path.join(output_dir, f"{safe_base_name}.webp")

        pixel_bean = PixelBeanDecoder.decode_file(dat_path)
        if pixel_bean is None:
            try:
                file_id = os.path.basename(dat_path).split('_')[0]
                print(f"  [SKIP] Unsupported or failed decode (ID: {file_id})")
            except:
                print(f"  [SKIP] Unsupported or failed decode")
            return ""

        pixel_bean.save_to_webp(
            out_path,
            scale=scale,
            target_width=target_width,
            target_height=target_height,
        )
        print(f"  [OK] Decoded -> {os.path.basename(out_path)}")
        return out_path
    except Exception as e:
        try:
            file_id = os.path.basename(dat_path).split('_')[0]
            print(f"  [ERROR] Decode failed (ID: {file_id}): {e}")
        except:
            print(f"  [ERROR] Decode failed: {e}")
        return ""


def decode_dat_files(
    file_paths: List[str],
    output_dir: str = None,
    scale: Union[int, float] = 1,
    target_width: int = None,
    target_height: int = None,
) -> List[str]:
    """
    Decode multiple downloaded .dat files to lossless WebP animations.

    Args:
        file_paths: List of .dat file paths
        output_dir: Output directory for .webp files (default: Config.OUTPUT_DIR)
        scale: Optional scale factor
        target_width: Optional explicit width
        target_height: Optional explicit height

    Returns:
        List of generated .webp file paths
    """
    if not file_paths:
        print("No .dat files to decode.")
        return []

    print("\n" + "-" * 70)
    print("Decoding downloaded DAT files to lossless WebP...")
    outputs: List[str] = []
    for i, path in enumerate(file_paths, 1):
        # Extract file ID to avoid Unicode issues with emoji filenames
        base_name = os.path.basename(path)
        try:
            file_id = base_name.split('_')[0]
            print(f"  [{i}/{len(file_paths)}] File ID: {file_id}")
        except:
            print(f"  [{i}/{len(file_paths)}] Processing...")
        
        out = decode_dat_file(
            path,
            output_dir=output_dir,
            scale=scale,
            target_width=target_width,
            target_height=target_height,
        )
        if out:
            outputs.append(out)

    print(f"\n[OK] Decoded {len(outputs)}/{len(file_paths)} files")
    return outputs


def test_download_and_decode_someone_arts(target_user_id: int, output_dir: str = None, debug: bool = False, **kwargs):
    """
    Test function to download and decode someone's arts.
    
    Args:
        target_user_id: ID of the user whose arts to download and decode
        output_dir: Directory to save decoded WebP files (default: Config.OUTPUT_DIR)
        debug: Enable verbose debugging output (default False)
        **kwargs: Additional parameters to pass to the download API
    
    Returns:
        Tuple of (list of downloaded .dat paths, list of decoded .webp paths)
    """
    try:
        from .client import sanitize_filename
    except ImportError:
        from servoom.client import sanitize_filename
    
    print("=" * 70)
    print("Testing Download and Decode Someone's Arts")
    print("=" * 70)
    
    # Step 1: Download the .dat files
    downloaded_files = test_download_someone_arts(target_user_id, debug=debug, **kwargs)
    
    if not downloaded_files:
        print("\n[INFO] No files downloaded, nothing to decode")
        return [], []
    
    # Step 2: Decode the downloaded files with proper naming
    if output_dir is None:
        output_dir = Config.OUTPUT_DIR + f'/{target_user_id}' + '/' + datetime.now().strftime('%Y-%m-%d')
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "-" * 70)
    print("Decoding downloaded DAT files to lossless WebP...")
    decoded_files = []
    
    for i, dat_path in enumerate(downloaded_files, 1):
        # Parse the filename: {gallery_id}_{artwork_name}.dat
        base_name = os.path.splitext(os.path.basename(dat_path))[0]
        
        try:
            # Split on first underscore to get gallery_id and artwork_name
            parts = base_name.split('_', 1)
            if len(parts) >= 2:
                gallery_id = parts[0]
                artwork_name = parts[1]
                
                # Sanitize the artwork name thoroughly
                # Remove or replace invalid characters
                safe_artwork_name = sanitize_filename(artwork_name)
                
                # Remove any remaining non-ASCII characters for safety
                safe_artwork_name = safe_artwork_name.encode('ascii', 'ignore').decode('ascii')
                
                # Remove multiple underscores/spaces
                safe_artwork_name = re.sub(r'[_\s]+', '_', safe_artwork_name)
                
                # Trim to reasonable length (leaving room for gallery_id and extension)
                max_name_length = 150
                if len(safe_artwork_name) > max_name_length:
                    safe_artwork_name = safe_artwork_name[:max_name_length]
                
                # Construct output filename: {gallery_id}_{safe_artwork_name}
                output_filename = f"{gallery_id}_{safe_artwork_name}"
                
                print(f"  [{i}/{len(downloaded_files)}] {gallery_id}: {safe_artwork_name}")
            else:
                # Fallback: just use gallery_id
                gallery_id = parts[0]
                output_filename = gallery_id
                print(f"  [{i}/{len(downloaded_files)}] {gallery_id}")
        except Exception as e:
            # Fallback: use the full base_name
            output_filename = sanitize_filename(base_name)
            print(f"  [{i}/{len(downloaded_files)}] Processing...")
        
        # Decode with custom output filename
        out_path = decode_dat_file(
            dat_path,
            output_dir=output_dir,
            output_filename=output_filename
        )
        
        if out_path:
            decoded_files.append(out_path)
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Downloaded {len(downloaded_files)} files, decoded {len(decoded_files)} files")
    print("=" * 70)
    
    return downloaded_files, decoded_files


def test_download_and_decode_my_arts(output_dir: str = None):
    """
    Test function to download and decode my own arts.
    
    Args:
        output_dir: Directory to save decoded WebP files (default: Config.OUTPUT_DIR)
    
    Returns:
        Tuple of (list of downloaded .dat paths, list of decoded .webp paths)
    """
    print("=" * 70)
    print("Testing Download and Decode My Arts")
    print("=" * 70)
    
    # Step 1: Download the .dat files
    downloaded_files = test_download_my_arts()
    
    if not downloaded_files:
        print("\n[INFO] No files downloaded, nothing to decode")
        return [], []
    
    # Step 2: Decode the downloaded files
    decoded_files = decode_dat_files(downloaded_files, output_dir=output_dir)
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Downloaded {len(downloaded_files)} files, decoded {len(decoded_files)} files")
    print("=" * 70)
    
    return downloaded_files, decoded_files


# ============================================================================
# REFERENCE ANIMATIONS VALIDATION
# ============================================================================

def _compose_gif_frames(gif_path: str, target_size: tuple) -> list:
    from PIL import Image, ImageSequence  # type: ignore
    frames = []
    with Image.open(gif_path) as im:  # type: ignore
        palette = im.getpalette()
        composed = None
        for frame in ImageSequence.Iterator(im):
            if frame.mode == 'P' and not frame.getpalette() and palette:
                frame.putpalette(palette)
            base = Image.new('RGBA', im.size, (255, 255, 255, 255))
            if composed is not None:
                base.paste(composed)
            rgba = frame.convert('RGBA')
            base.paste(rgba, (0, 0), rgba)
            composed = base
            rgb = base.convert('RGB')
            if rgb.size != target_size:
                rgb = rgb.resize(target_size, Image.NEAREST)
            frames.append(rgb)
    return frames


def _avg_abs_rgb_diff(img_a, img_b) -> float:
    # Compute mean absolute per-channel difference
    a = img_a.tobytes()
    b = img_b.tobytes()
    total = 0
    length = min(len(a), len(b))
    for i in range(length):
        total += abs(a[i] - b[i])
    if length == 0:
        return 255.0
    return total / float(length)


def decode_reference_animations(output_dir: str = None, threshold: float = 20.0) -> None:
    import glob
    from PIL import Image  # type: ignore
    if output_dir is None:
        output_dir = Config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    dat_dir = os.path.join('reference-animations', 'DAT')
    gif_dir = os.path.join('reference-animations', 'GIF-WEBP')
    dat_paths = sorted(glob.glob(os.path.join(dat_dir, '*.dat')))
    if not dat_paths:
        print('[INFO] No reference DAT files found')
        return

    # Build a normalized map of GIF basenames -> path for flexible matching
    def _normalize_name(name: str) -> str:
        base = os.path.splitext(os.path.basename(name))[0]
        base = base.replace('+', ' ')
        base = ' '.join(base.split())
        return base.lower()

    gif_paths = sorted(glob.glob(os.path.join(gif_dir, '*.gif')))
    gif_map = {_normalize_name(p): p for p in gif_paths}

    passed = 0
    total = 0
    for dat_path in dat_paths:
        base = os.path.splitext(os.path.basename(dat_path))[0]
        # Attempt to resolve matching GIF filename in a flexible way
        dat_norm = base
        if '_' in dat_norm:
            dat_norm = dat_norm.split('_', 1)[1]
        dat_norm = dat_norm.replace('+', ' ')
        dat_norm = ' '.join(dat_norm.split())
        gif_path = gif_map.get(dat_norm.lower(), '')
        print(f"Decoding reference: {base}")
        try:
            pb = PixelBeanDecoder.decode_file(dat_path)
            if pb is None:
                print(f"  [SKIP] Unsupported format: {base}")
                continue
            # Save to webp
            out_webp = os.path.join(output_dir, f"ref_{base}.webp")
            pb.save_to_webp(out_webp)

            # Compare to GIF/WebP if present
            if gif_path and os.path.exists(gif_path):
                ref_frames = _compose_gif_frames(gif_path, (pb.width, pb.height))
                num = min(len(ref_frames), pb.total_frames)
                if num == 0:
                    print(f"  [WARN] No frames to compare: {base}")
                    continue
                diffs = []
                for i in range(num):
                    img_pb = pb.get_frame_image(i + 1)
                    diff = _avg_abs_rgb_diff(img_pb, ref_frames[i])
                    diffs.append(diff)
                avg = sum(diffs) / len(diffs)
                total += 1
                if avg <= threshold:
                    passed += 1
                    print(f"  [OK] Avg abs RGB diff {avg:.2f} <= {threshold}")
                else:
                    print(f"  [WARN] Avg abs RGB diff {avg:.2f} > {threshold}")
            else:
                print(f"  [INFO] No reference GIF match for: {base}")
        except Exception as e:
            print(f"  [ERROR] Failed {base}: {e}")
    if total:
        print(f"\n[RESULT] Passed {passed}/{total} ({passed/total*100:.1f}%) within threshold {threshold}")
    else:
        print("\n[INFO] No comparisons performed")


def decode_and_compare_format_26():
    """
    Decode DAT files from reference-animations/26/DAT and compare them
    frame-by-frame, pixel-by-pixel with corresponding WebP files in
    reference-animations/26/WEBP.
    
    Returns:
        Dictionary mapping filenames to comparison results
    """
    import glob
    from PIL import Image, ImageSequence  # type: ignore
    
    print("=" * 70)
    print("Decoding and Comparing Format 26 Reference Animations")
    print("=" * 70)
    
    dat_dir = os.path.join('reference-animations', '26', 'DAT')
    webp_dir = os.path.join('reference-animations', '26', 'WEBP')
    
    # Check directories exist
    if not os.path.exists(dat_dir):
        print(f"\n[ERROR] DAT directory not found: {dat_dir}")
        return {}
    
    if not os.path.exists(webp_dir):
        print(f"\n[ERROR] WEBP directory not found: {webp_dir}")
        return {}
    
    # Get all DAT files
    dat_paths = sorted(glob.glob(os.path.join(dat_dir, '*.dat')))
    if not dat_paths:
        print(f"\n[INFO] No DAT files found in {dat_dir}")
        return {}
    
    print(f"\nFound {len(dat_paths)} DAT files to process")
    print("-" * 70)
    
    results = {}
    
    for dat_path in dat_paths:
        # Get base filename without extension
        base_name = os.path.splitext(os.path.basename(dat_path))[0]
        webp_path = os.path.join(webp_dir, f"{base_name}.webp")
        
        print(f"\nProcessing: {base_name}")
        
        # Check if corresponding WebP exists
        if not os.path.exists(webp_path):
            print(f"  [SKIP] No corresponding WebP file found: {webp_path}")
            results[base_name] = {"status": "NO_REFERENCE"}
            continue
        
        try:
            # Decode DAT file
            pixel_bean = PixelBeanDecoder.decode_file(dat_path)
            
            if pixel_bean is None:
                print(f"  [SKIP] Failed to decode DAT file")
                results[base_name] = {"status": "DECODE_FAILED"}
                continue
            
            decoded_frames = pixel_bean.total_frames
            decoded_width = pixel_bean.width
            decoded_height = pixel_bean.height
            
            # Read WebP frames
            ref_frames = []
            with Image.open(webp_path) as im:
                # Ensure dimensions match
                if im.size != (decoded_width, decoded_height):
                    print(f"  [WARN] Dimension mismatch: DAT={decoded_width}x{decoded_height}, WebP={im.size[0]}x{im.size[1]}")
                    # Resize reference frames to match decoded dimensions
                    for frame in ImageSequence.Iterator(im):
                        rgb_frame = frame.convert('RGB')
                        if rgb_frame.size != (decoded_width, decoded_height):
                            rgb_frame = rgb_frame.resize((decoded_width, decoded_height), Image.NEAREST)
                        ref_frames.append(rgb_frame)
                else:
                    for frame in ImageSequence.Iterator(im):
                        ref_frames.append(frame.convert('RGB'))
            
            ref_frames_count = len(ref_frames)
            
            # Compare frame counts
            if decoded_frames != ref_frames_count:
                print(f"  [NO MATCH] Frame count mismatch: DAT={decoded_frames}, WebP={ref_frames_count}")
                results[base_name] = {
                    "status": "NO_MATCH",
                    "decoded_frames": decoded_frames,
                    "reference_frames": ref_frames_count
                }
                continue
            
            # Frame counts match - proceed with pixel-by-pixel comparison
            print(f"  Frame count: {decoded_frames} (match)")
            print(f"  Dimensions: {decoded_width}x{decoded_height}")
            
            total_pixels = 0
            matching_pixels = 0
            
            for frame_idx in range(decoded_frames):
                # Get decoded frame (1-indexed)
                decoded_img = pixel_bean.get_frame_image(frame_idx + 1)
                decoded_img = decoded_img.convert('RGB')
                
                # Get reference frame
                ref_img = ref_frames[frame_idx]
                
                # Ensure same size
                if decoded_img.size != ref_img.size:
                    ref_img = ref_img.resize(decoded_img.size, Image.NEAREST)
                
                # Convert to numpy arrays for pixel comparison
                decoded_array = np.array(decoded_img)
                ref_array = np.array(ref_img)
                
                # Count matching pixels (exact RGB match)
                frame_pixels = decoded_array.shape[0] * decoded_array.shape[1]
                total_pixels += frame_pixels
                
                # Compare pixel-by-pixel (all 3 RGB channels must match exactly)
                matches = np.all(decoded_array == ref_array, axis=2)
                frame_matching_pixels = np.sum(matches)
                matching_pixels += frame_matching_pixels
            
            # Calculate match percentage
            if total_pixels > 0:
                match_percentage = (matching_pixels / total_pixels) * 100.0
                print(f"  MATCH = {match_percentage:.2f}% ({matching_pixels}/{total_pixels} pixels)")
                results[base_name] = {
                    "status": "MATCH",
                    "match_percentage": match_percentage,
                    "matching_pixels": int(matching_pixels),
                    "total_pixels": int(total_pixels),
                    "frames": decoded_frames
                }
            else:
                print(f"  [ERROR] No pixels to compare")
                results[base_name] = {"status": "ERROR", "message": "No pixels to compare"}
                
        except Exception as e:
            print(f"  [ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()
            results[base_name] = {"status": "ERROR", "message": str(e)}
    
    # Print summary
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    
    no_match_count = sum(1 for r in results.values() if r.get("status") == "NO_MATCH")
    match_count = sum(1 for r in results.values() if r.get("status") == "MATCH")
    other_count = len(results) - no_match_count - match_count
    
    print(f"  Total files processed: {len(results)}")
    print(f"  NO MATCH (frame count): {no_match_count}")
    print(f"  MATCH (pixel comparison): {match_count}")
    print(f"  Other (skipped/errors): {other_count}")
    
    if match_count > 0:
        print("\n  Match percentages:")
        for name, result in sorted(results.items()):
            if result.get("status") == "MATCH":
                print(f"    {name}: {result['match_percentage']:.2f}%")
    
    print("=" * 70)
    
    return results


def test_decode_format_31():
    """
    Test function to decode a specific format 31 file for debugging.
    """
    import os
    
    print("=" * 70)
    print("Testing Format 31 Decoder")
    print("=" * 70)
    
    # Path to the specific file
    dat_file = os.path.join("downloads", "401670591", "3844557_🐜🐜🐜🐜🐜.dat")
    
    if not os.path.exists(dat_file):
        print(f"\n[ERROR] File not found")
        return None
    
    print(f"\nDecoding file from: downloads/401670591/")
    print(f"File ID: 3844557")
    print(f"File size: {os.path.getsize(dat_file)} bytes")
    
    try:
        # Decode the file
        pixel_bean = PixelBeanDecoder.decode_file(dat_file)
        
        if pixel_bean is None:
            print("\n[ERROR] Decoding failed, returned None")
            return None
        
        print(f"\n[SUCCESS] Decoded successfully!")
        print(f"  Frames: {pixel_bean.total_frames}")
        print(f"  Dimensions: {pixel_bean.width}x{pixel_bean.height}")
        print(f"  Speed: {pixel_bean.speed} ms")
        
        # Try to save as WebP to verify it works
        output_path = os.path.join(Config.OUTPUT_DIR, "test_format_31.webp")
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        pixel_bean.save_to_webp(output_path)
        print(f"  Saved to: {output_path}")
        
        return pixel_bean
        
    except Exception as e:
        print(f"\n[ERROR] Exception during decoding: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Display debug mode status
    if Config.DEBUG_MODE:
        print("=" * 70)
        print(f"[!] DEBUG MODE ACTIVE - Output limited to {Config.DEBUG_LIMIT} items")
        print("=" * 70)
        print()
    
    # ========================================================================
    # Test downloading and decoding arts
    # ========================================================================
    
    # Decode local reference animations and compare against GIFs
    # decode_reference_animations()
    
    # Test download and decode my own arts (limited by DEBUG_LIMIT)
    # test_download_and_decode_my_arts()
    
    # ========================================================================
    # Default behavior: run the full data fetcher (commented out for testing)
    # ========================================================================
    
    # fetcher = DivoomDataFetcher()
    # fetcher.run()
    
    # ========================================================================
    # DEBUG/TESTING - Other endpoint tests
    # ========================================================================
    
    # # Test fetch my arts (✓ Working)
    # test_fetch_my_arts()
    
    # # Test download only (without decode)
    # test_download_someone_arts(403794905)  # badguy's user ID
    # test_download_and_decode_someone_arts(403939019) # Cinnamorol18's user ID	
    # test_download_and_decode_someone_arts(401670591) # monsters's user ID
    # test_download_and_decode_someone_arts(403017293) # Fab's user ID
    
    # Test format 31 decoder on single file
    # test_decode_format_31()
    
    # # Test batch decode of already downloaded files (format 31 included)
    # import glob
    # dat_files = glob.glob("downloads/401670591/*.dat")
    # if dat_files:
    #     print(f"\nFound {len(dat_files)} DAT files to decode")
    #     
    #     # First, scan all files to count format types
    #     print("\nScanning file formats...")
    #     format_counts = {}
    #     for dat_file in dat_files[:50]:  # Scan first 50 (respecting DEBUG_MODE)
    #         try:
    #             with open(dat_file, 'rb') as f:
    #                 fmt = f.read(1)[0]
    #                 format_counts[fmt] = format_counts.get(fmt, 0) + 1
    #         except:
    #             pass
    #     
    #     print("Format distribution:")
    #     for fmt, count in sorted(format_counts.items()):
    #         print(f"  Format {fmt}: {count} files")
    #     
    #     # Now decode files
    #     decoded_files = decode_dat_files(dat_files[:30])  # Decode first 30 for testing
    #     print(f"\n[SUCCESS] Decoded {len(decoded_files)} files")
    
    # # Test format 31 with full batch decode
    # test_download_and_decode_someone_arts(401670591)  # monsters's user ID (has format 31 files)
    # test_download_and_decode_someone_arts(403794905) # badguy's user ID
    # test_download_and_decode_someone_arts(400568695) # LeCDrom's user ID
    # test_download_and_decode_someone_arts(401553003) # fantabulicious's user ID
    
    # # Test SearchUser endpoint (✓ Working)
    # test_search_user("fantabulicious")
    # test_search_user("badguy")
    
    # # Test fetch someone's arts (✓ Working)
    # test_fetch_someone_arts(401353363)
    
    # # Test GetSomeoneInfoV2 endpoint
    # test_fetch_someone_info(401353363) # Sendewa's user ID
    
    # Test Manager/GetReportGallery endpoint
    # test_fetch_report_gallery()
    
    # Test GetCategoryFileListV2 endpoint
    # test_fetch_category_files(18)
    test_download_and_decode_gallery_files(18)

    # Test decode and compare format 26 reference animations
    # decode_and_compare_format_26()

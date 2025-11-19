"""
Test and utility functions for servoom package.
Moved from cli.py as part of refactoring.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Union

from PIL import Image, ImageSequence

from servoom import DivoomClient, PixelBean, PixelBeanDecoder
from servoom.config import Config
from servoom.client import sanitize_filename, safe_console_text


# ============================================================================
# USER ID CONSTANTS
# ============================================================================

# User IDs for testing (declare at top, reuse as needed)
USER_ID_BADGUY = 403794905
USER_ID_CINNAMOROLL18 = 403939019
USER_ID_MONSTERS = 401670591
USER_ID_FAB = 403017293
USER_ID_LECDROM = 400568695
USER_ID_FANTABULICIOUS = 401553003
USER_ID_SENDEWA = 401353363


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def append_timestamp(filename: str) -> str:
    """Append current timestamp to filename."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name, file_extension = os.path.splitext(filename)
    return f"{file_name}_{timestamp}{file_extension}"


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
            safe_base_name = output_filename
        else:
            base_name = os.path.splitext(os.path.basename(dat_path))[0]
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


def decode_dat_folder(folder: Path, output: Path):
    """Decode all .dat files in a folder."""
    output.mkdir(parents=True, exist_ok=True)
    for dat_file in sorted(folder.glob('*.dat')):
        bean = PixelBeanDecoder.decode_file(str(dat_file))
        if bean:
            out_path = output / (dat_file.stem + '.webp')
            bean.save_to_webp(str(out_path))
            print(f"Decoded {dat_file.name} -> {out_path}")


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_fetch_my_arts(export_csv: bool = True, debug: bool = False, **kwargs):
    """Test function to fetch my own arts with debugging enabled."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print("Testing GetMyUploadListV3 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
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
            # Convert to PixelBeans and export
            beans = [PixelBean(metadata=art) for art in arts_data]
            client.export_artworks_to_csv(beans, base_filename='my_arts')
        
        return arts_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fetch_someone_arts(target_user_id: int, export_csv: bool = True, debug: bool = True, **kwargs):
    """Test function to fetch another user's arts with debugging enabled."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print("Testing GetSomeoneListV3 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
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
            beans = [PixelBean(metadata=art) for art in arts_data]
            client.export_artworks_to_csv(beans, base_filename=f'someone_arts_{target_user_id}')
        
        return arts_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_download_and_decode_someone_arts(target_user_id: int, output_dir: str = None, debug: bool = False, **kwargs):
    """Test function to download and decode someone's arts."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print("Testing Download and Decode Someone's Arts")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    if not client.login():
        return [], []
    
    # Step 1: Download the .dat files
    downloaded_files = client.download_someone_arts(target_user_id, debug=debug, **kwargs)
    
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
        base_name = os.path.splitext(os.path.basename(dat_path))[0]
        
        try:
            parts = base_name.split('_', 1)
            if len(parts) >= 2:
                gallery_id = parts[0]
                artwork_name = parts[1]
                
                safe_artwork_name = sanitize_filename(artwork_name)
                safe_artwork_name = safe_artwork_name.encode('ascii', 'ignore').decode('ascii')
                safe_artwork_name = re.sub(r'[_\s]+', '_', safe_artwork_name)
                
                max_name_length = 150
                if len(safe_artwork_name) > max_name_length:
                    safe_artwork_name = safe_artwork_name[:max_name_length]
                
                output_filename = f"{gallery_id}_{safe_artwork_name}"
                print(f"  [{i}/{len(downloaded_files)}] {gallery_id}: {safe_artwork_name}")
            else:
                gallery_id = parts[0]
                output_filename = gallery_id
                print(f"  [{i}/{len(downloaded_files)}] {gallery_id}")
        except Exception as e:
            output_filename = sanitize_filename(base_name)
            print(f"  [{i}/{len(downloaded_files)}] Processing...")
        
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
    """Test function to download and decode my own arts."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print("Testing Download and Decode My Arts")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    if not client.login():
        return [], []
    
    # Step 1: Download the .dat files
    downloaded_files = client.download_my_arts()
    
    if not downloaded_files:
        print("\n[INFO] No files downloaded, nothing to decode")
        return [], []
    
    # Step 2: Decode the downloaded files
    decoded_files = decode_dat_files(downloaded_files, output_dir=output_dir)
    
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Downloaded {len(downloaded_files)} files, decoded {len(decoded_files)} files")
    print("=" * 70)
    
    return downloaded_files, decoded_files


def test_fetch_category_files(category_id: int, export_csv: bool = False, debug: bool = True, **kwargs):
    """Test function to fetch files from a specific category."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print("Testing GetCategoryFileListV2 Endpoint")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
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
            beans = [PixelBean(metadata=file_data) for file_data in files_data]
            client.export_artworks_to_csv(beans, base_filename=f'category_{category_id}_files')
        
        return files_data
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_download_art_by_id(gallery_id: int, output_dir: str = None):
    """Test function to download an artwork by its gallery ID."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print(f"Testing Download Art by ID: {gallery_id}")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    if not client.login():
        return None, None
    
    try:
        # Download by ID
        pixel_bean, file_path = client.download_art_by_id(gallery_id, output_dir=output_dir)
        
        print(f"\n[SUCCESS] Downloaded artwork!")
        print(f"  Gallery ID: {pixel_bean.gallery_id}")
        print(f"  File Name: {safe_console_text(pixel_bean.file_name)}")
        print(f"  File Path: {file_path}")
        print(f"  State: {pixel_bean.state.value}")
        
        return pixel_bean, file_path
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def decode_reference_animations(output_dir: str = None, threshold: float = 20.0) -> None:
    """Decode reference animations and compare against GIFs."""
    import glob
    
    if output_dir is None:
        output_dir = Config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    dat_dir = os.path.join('reference-animations', 'DAT')
    gif_dir = os.path.join('reference-animations', 'GIF-WEBP')
    dat_paths = sorted(glob.glob(os.path.join(dat_dir, '*.dat')))
    if not dat_paths:
        print('[INFO] No reference DAT files found')
        return

    def _normalize_name(name: str) -> str:
        base = os.path.splitext(os.path.basename(name))[0]
        base = base.replace('+', ' ')
        base = ' '.join(base.split())
        return base.lower()

    gif_paths = sorted(glob.glob(os.path.join(gif_dir, '*.gif')))
    gif_map = {_normalize_name(p): p for p in gif_paths}

    def _compose_gif_frames(gif_path: str, target_size: tuple) -> list:
        frames = []
        with Image.open(gif_path) as im:
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
        a = img_a.tobytes()
        b = img_b.tobytes()
        total = 0
        length = min(len(a), len(b))
        for i in range(length):
            total += abs(a[i] - b[i])
        if length == 0:
            return 255.0
        return total / float(length)

    passed = 0
    total = 0
    for dat_path in dat_paths:
        base = os.path.splitext(os.path.basename(dat_path))[0]
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
            out_webp = os.path.join(output_dir, f"ref_{base}.webp")
            pb.save_to_webp(out_webp)

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


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def fetch_and_decode_artworks(gallery_ids: List[int], output_dir: str = None):
    """
    Fetch and decode multiple artworks by their gallery IDs.
    
    Args:
        gallery_ids: List of gallery IDs to fetch and decode
        output_dir: Directory to save downloaded and decoded files (default: Config.OUTPUT_DIR)
    """
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    print("=" * 70)
    print("Fetching and Decoding Artworks")
    print("=" * 70)
    
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    if not client.login():
        print("[ERROR] Failed to login")
        return
    
    if output_dir is None:
        output_dir = Config.OUTPUT_DIR
    
    os.makedirs(output_dir, exist_ok=True)
    
    downloaded_files = []
    decoded_files = []
    
    for i, gallery_id in enumerate(gallery_ids, 1):
        print(f"\n[{i}/{len(gallery_ids)}] Processing Gallery ID: {gallery_id}")
        print("-" * 70)
        
        try:
            # Download artwork
            pixel_bean, file_path = client.download_art_by_id(gallery_id, output_dir=output_dir)
            downloaded_files.append(file_path)
            
            print(f"  Artwork: {safe_console_text(pixel_bean.file_name)}")
            
            # Decode artwork
            client.decode_art(pixel_bean)
            
            # Save decoded WebP
            webp_filename = os.path.splitext(os.path.basename(file_path))[0] + '.webp'
            webp_path = os.path.join(output_dir, webp_filename)
            pixel_bean.save_to_webp(webp_path)
            decoded_files.append(webp_path)
            
            print(f"  Decoded: {safe_console_text(webp_filename)}")
            print(f"  Frames: {pixel_bean.total_frames}, Size: {pixel_bean.width}x{pixel_bean.height}")
            
        except Exception as e:
            print(f"  [ERROR] Failed to process gallery ID {gallery_id}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Downloaded: {len(downloaded_files)}/{len(gallery_ids)} files")
    print(f"  Decoded: {len(decoded_files)}/{len(gallery_ids)} files")
    print(f"  Output directory: {output_dir}")
    print("=" * 70)


def main():
    """Main test function."""
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD
    
    # Display debug mode status
    if Config.DEBUG_MODE:
        print("=" * 70)
        print(f"[!] DEBUG MODE ACTIVE - Output limited to {Config.DEBUG_LIMIT} items")
        print("=" * 70)
        print()
    
    # Fetch and decode specific artworks
    # Focus on 2947079 for debugging
    # artwork_ids = [3981085]  # Temporarily focus on one file
    # fetch_and_decode_artworks(artwork_ids)
    
    # Example: Decode reference animations
    # decode_reference_animations()
    
    # Example: Test download and decode my own arts
    # test_download_and_decode_my_arts()
    
    # Example: Test download and decode someone's arts
    test_download_and_decode_someone_arts(USER_ID_MONSTERS)
    
    # Example: Decode local reference animations
    # client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    # client.login()
    
    # mixed_dir = Path('reference-animations/mixed/DAT')
    # out_dir = Path('decoded-mixed-clean')
    # decode_dat_folder(mixed_dir, out_dir)


if __name__ == '__main__':
    main()

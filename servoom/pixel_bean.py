from typing import Union, List, Optional, Dict
from enum import Enum

import numpy as np
from PIL import Image


class PixelBeanState(Enum):
    """Lifecycle state of a PixelBean."""
    METADATA_ONLY = "metadata_only"  # Only has metadata, no file downloaded
    DOWNLOADED = "downloaded"  # File downloaded but not decoded
    COMPLETE = "complete"  # File downloaded and decoded


class PixelBean(object):
    """
    Represents a Divoom artwork with metadata and optional animation data.
    
    Can be created in three ways:
    1. From metadata only (state: METADATA_ONLY)
    2. From metadata + local file path (state: DOWNLOADED)
    3. From decoded animation data (state: COMPLETE)
    """
    
    @property
    def total_frames(self):
        """Number of frames in the animation (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._total_frames

    @property
    def speed(self):
        """Frame delay in milliseconds (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._speed

    @property
    def row_count(self):
        """Number of 16x16 tile rows (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._row_count

    @property
    def column_count(self):
        """Number of 16x16 tile columns (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._column_count

    @property
    def frames_data(self):
        """List of numpy arrays with frame data (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._frames_data

    @property
    def width(self):
        """Frame width in pixels (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._width

    @property
    def height(self):
        """Frame height in pixels (only available when decoded)."""
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        return self._height
    
    @property
    def state(self) -> PixelBeanState:
        """Current lifecycle state of this PixelBean."""
        return self._state
    
    @property
    def file_path(self) -> Optional[str]:
        """Path to the downloaded Divoom file (None if not downloaded)."""
        return self._file_path
    
    @property
    def metadata(self) -> Dict:
        """Artwork metadata dictionary."""
        return self._metadata.copy()
    
    @property
    def gallery_id(self) -> Optional[int]:
        """Gallery ID from metadata."""
        return self._metadata.get('GalleryId')
    
    @property
    def file_id(self) -> Optional[str]:
        """File ID from metadata."""
        return self._metadata.get('FileId')
    
    @property
    def file_name(self) -> Optional[str]:
        """File name from metadata."""
        return self._metadata.get('FileName')

    def __init__(
        self,
        metadata: Dict,
        file_path: Optional[str] = None,
        total_frames: Optional[int] = None,
        speed: Optional[int] = None,
        row_count: Optional[int] = None,
        column_count: Optional[int] = None,
        frames_data: Optional[List[np.ndarray]] = None,
    ):
        """
        Initialize PixelBean.
        
        Args:
            metadata: Dictionary containing artwork metadata (must include GalleryId, FileId, FileName, etc.)
            file_path: Optional path to downloaded Divoom file (.dat)
            total_frames: Number of frames (required if frames_data provided)
            speed: Frame delay in milliseconds (required if frames_data provided)
            row_count: Number of 16x16 tile rows (required if frames_data provided)
            column_count: Number of 16x16 tile columns (required if frames_data provided)
            frames_data: List of numpy arrays (one per frame), each of shape (height, width, 3) with RGB values
            
        Note:
            - If only metadata provided: state = METADATA_ONLY
            - If metadata + file_path provided: state = DOWNLOADED
            - If metadata + file_path + frames_data provided: state = COMPLETE
        """
        self._metadata = metadata.copy()
        self._file_path = file_path
        
        # Determine state and validate
        if frames_data is not None:
            # Complete: has decoded animation data
            if total_frames is None or speed is None or row_count is None or column_count is None:
                raise ValueError("total_frames, speed, row_count, and column_count required when frames_data provided")
            self._state = PixelBeanState.COMPLETE
            self._total_frames = total_frames
            self._speed = speed
            self._row_count = row_count
            self._column_count = column_count
            self._frames_data = frames_data
            self._width = column_count * 16
            self._height = row_count * 16
        elif file_path is not None:
            # Downloaded: has file but not decoded
            self._state = PixelBeanState.DOWNLOADED
            self._total_frames = None
            self._speed = None
            self._row_count = None
            self._column_count = None
            self._frames_data = None
            self._width = None
            self._height = None
        else:
            # Metadata only
            self._state = PixelBeanState.METADATA_ONLY
            self._total_frames = None
            self._speed = None
            self._row_count = None
            self._column_count = None
            self._frames_data = None
            self._width = None
            self._height = None
    
    def update_from_download(self, file_path: str) -> None:
        """
        Update PixelBean after file has been downloaded.
        
        Args:
            file_path: Path to the downloaded Divoom file
        """
        self._file_path = file_path
        if self._state == PixelBeanState.METADATA_ONLY:
            self._state = PixelBeanState.DOWNLOADED
    
    def update_from_decode(
        self,
        total_frames: int,
        speed: int,
        row_count: int,
        column_count: int,
        frames_data: List[np.ndarray],
    ) -> None:
        """
        Update PixelBean with decoded animation data.
        
        Args:
            total_frames: Number of frames in the animation
            speed: Frame delay in milliseconds
            row_count: Number of 16x16 tile rows
            column_count: Number of 16x16 tile columns
            frames_data: List of numpy arrays (one per frame), each of shape (height, width, 3) with RGB values
        """
        if self._state == PixelBeanState.METADATA_ONLY:
            raise ValueError("Cannot decode: file not downloaded. Please download the file first.")
        
        self._total_frames = total_frames
        self._speed = speed
        self._row_count = row_count
        self._column_count = column_count
        self._frames_data = frames_data
        self._width = column_count * 16
        self._height = row_count * 16
        self._state = PixelBeanState.COMPLETE

    def get_frame_image(
        self,
        frame_number: int,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> Image:
        """
        Get Pillow Image of a frame.
        
        Args:
            frame_number: Frame number (1-indexed)
            scale: Optional scale factor
            target_width: Optional target width
            target_height: Optional target height
            
        Returns:
            PIL Image object
            
        Raises:
            ValueError: If animation not decoded yet
        """
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        
        if frame_number <= 0 or frame_number > self.total_frames:
            raise Exception('Frame number out of range!')

        # Get the frame as a numpy array (height, width, 3) with RGB values
        frame_array = self._frames_data[frame_number - 1]
        
        # Convert numpy array to PIL Image
        # numpy array is already in RGB format with shape (height, width, 3)
        img = Image.fromarray(frame_array.astype(np.uint8), 'RGB')

        img = self._resize(
            img, scale=scale, target_width=target_width, target_height=target_height
        )
        return img

    def _resize(
        self,
        img: Image,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> Image:
        """
        Resize image based on scale or target dimensions.
        
        Args:
            img: PIL Image to resize
            scale: Scale factor (default 1, no scaling)
            target_width: Optional explicit target width
            target_height: Optional explicit target height
            
        Returns:
            Resized PIL Image
        """
        if target_width is not None and target_height is not None:
            return img.resize((target_width, target_height), Image.NEAREST)
        elif target_width is not None:
            new_height = int(img.height * target_width / img.width)
            return img.resize((target_width, new_height), Image.NEAREST)
        elif target_height is not None:
            new_width = int(img.width * target_height / img.height)
            return img.resize((new_width, target_height), Image.NEAREST)
        elif scale != 1:
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            return img.resize((new_width, new_height), Image.NEAREST)
        return img

    def save_to_webp(
        self,
        output_path: str,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> None:
        """
        Convert animation to WebP file.
        
        Args:
            output_path: Path to save WebP file
            scale: Optional scale factor
            target_width: Optional target width
            target_height: Optional target height
            
        Raises:
            ValueError: If animation not decoded yet
        """
        if self._state != PixelBeanState.COMPLETE:
            raise ValueError("Animation not decoded yet. Call decode() first.")
        
        webp_frames = []

        for frame_number in range(self._total_frames):
            img = self.get_frame_image(
                frame_number + 1,
                scale=scale,
                target_width=target_width,
                target_height=target_height,
            )
            webp_frames.append(img)

        # Save to WebP
        webp_frames[0].save(
            output_path,
            append_images=webp_frames[1:],
            duration=self._speed,
            save_all=True,
            loop=0,
            disposal=0,
            lossless=True
        )

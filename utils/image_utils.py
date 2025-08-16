"""
Image processing utilities for wound classification
"""

import os
import logging
from typing import Tuple, Dict, Optional, Union
from PIL import Image, ImageOps, ImageEnhance
import numpy as np
import cv2
from pathlib import Path

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Image processing utilities for wound analysis"""
    
    # Supported image formats
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = int(os.getenv('MAX_IMAGE_SIZE', 10 * 1024 * 1024))
    
    # Image size constraints
    MIN_SIZE = (32, 32)
    MAX_SIZE = (
        int(os.getenv('IMAGE_RESIZE_MAX_WIDTH', 1024)),
        int(os.getenv('IMAGE_RESIZE_MAX_HEIGHT', 1024))
    )

    @staticmethod
    def validate_image(image_path: str) -> bool:
        """
        Validate image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return False
            
            # Check file size
            file_size = os.path.getsize(image_path)
            if file_size > ImageProcessor.MAX_FILE_SIZE:
                logger.error(f"Image file too large: {file_size} bytes")
                return False
            
            if file_size == 0:
                logger.error("Image file is empty")
                return False
            
            # Check file extension
            file_ext = Path(image_path).suffix.lower()
            if file_ext not in ImageProcessor.SUPPORTED_FORMATS:
                logger.error(f"Unsupported image format: {file_ext}")
                return False
            
            # Try to open and validate image
            with Image.open(image_path) as img:
                # Check if image can be converted to RGB
                img.convert("RGB")
                
                # Check image dimensions
                if img.size[0] < ImageProcessor.MIN_SIZE[0] or img.size[1] < ImageProcessor.MIN_SIZE[1]:
                    logger.error(f"Image too small: {img.size}")
                    return False
                
                # Verify image is not corrupted
                img.verify()
            
            return True
            
        except Exception as e:
            logger.error(f"Image validation error: {str(e)}")
            return False

    @staticmethod
    def get_image_info(image_path: str) -> Dict:
        """
        Get image information
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary with image information
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'file_size': os.path.getsize(image_path),
                    'aspect_ratio': img.width / img.height,
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
        except Exception as e:
            logger.error(f"Error getting image info: {str(e)}")
            return {}

    @staticmethod
    def preprocess_image(image_path: str, 
                        target_size: Tuple[int, int] = (224, 224),
                        enhance_contrast: bool = False,
                        normalize: bool = True) -> np.ndarray:
        """
        Preprocess image for model input
        
        Args:
            image_path: Path to image file
            target_size: Target size for resizing
            enhance_contrast: Whether to enhance contrast
            normalize: Whether to normalize pixel values
            
        Returns:
            Preprocessed image array
        """
        try:
            # Load image
            with Image.open(image_path) as img:
                # Convert to RGB
                img = img.convert("RGB")
                
                # Resize image
                img = img.resize(target_size, Image.Resampling.LANCZOS)
                
                # Enhance contrast if requested
                if enhance_contrast:
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.2)
                
                # Convert to numpy array
                img_array = np.array(img)
                
                # Normalize if requested
                if normalize:
                    img_array = img_array.astype(np.float32) / 255.0
                
                return img_array
                
        except Exception as e:
            logger.error(f"Image preprocessing error: {str(e)}")
            raise

    @staticmethod
    def resize_image(image_path: str, 
                    output_path: str, 
                    max_size: Tuple[int, int] = None) -> bool:
        """
        Resize image while maintaining aspect ratio
        
        Args:
            image_path: Input image path
            output_path: Output image path
            max_size: Maximum dimensions
            
        Returns:
            True if successful, False otherwise
        """
        try:
            max_size = max_size or ImageProcessor.MAX_SIZE
            
            with Image.open(image_path) as img:
                # Convert to RGB
                img = img.convert("RGB")
                
                # Calculate new size maintaining aspect ratio
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save resized image
                img.save(output_path, "JPEG", quality=85, optimize=True)
                
            logger.info(f"Image resized: {image_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Image resize error: {str(e)}")
            return False

    @staticmethod
    def enhance_wound_image(image_path: str, 
                           output_path: str = None,
                           brightness: float = 1.1,
                           contrast: float = 1.2,
                           sharpness: float = 1.1) -> str:
        """
        Enhance wound image for better analysis
        
        Args:
            image_path: Input image path
            output_path: Output image path (if None, overwrites input)
            brightness: Brightness enhancement factor
            contrast: Contrast enhancement factor
            sharpness: Sharpness enhancement factor
            
        Returns:
            Path to enhanced image
        """
        try:
            output_path = output_path or image_path
            
            with Image.open(image_path) as img:
                # Convert to RGB
                img = img.convert("RGB")
                
                # Enhance brightness
                if brightness != 1.0:
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(brightness)
                
                # Enhance contrast
                if contrast != 1.0:
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(contrast)
                
                # Enhance sharpness
                if sharpness != 1.0:
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(sharpness)
                
                # Save enhanced image
                img.save(output_path, "JPEG", quality=90, optimize=True)
                
            logger.info(f"Image enhanced: {image_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Image enhancement error: {str(e)}")
            return image_path

    @staticmethod
    def detect_wound_region(image_path: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect potential wound region using simple color-based segmentation
        
        Args:
            image_path: Path to image file
            
        Returns:
            Bounding box (x, y, width, height) or None if not found
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                return None
                
            # Convert to HSV for better color segmentation
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Define color ranges for potential wound areas (reddish tones)
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            
            # Create masks
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask = cv2.bitwise_or(mask1, mask2)
            
            # Apply morphological operations
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find largest contour
                largest_contour = max(contours, key=cv2.contourArea)
                
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                # Filter by minimum size
                if w > 50 and h > 50:
                    return (x, y, w, h)
            
            return None
            
        except Exception as e:
            logger.error(f"Wound region detection error: {str(e)}")
            return None

    @staticmethod
    def crop_wound_region(image_path: str, 
                         output_path: str,
                         bbox: Tuple[int, int, int, int],
                         padding: int = 20) -> bool:
        """
        Crop image to wound region with padding
        
        Args:
            image_path: Input image path
            output_path: Output image path
            bbox: Bounding box (x, y, width, height)
            padding: Padding around the bounding box
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with Image.open(image_path) as img:
                x, y, w, h = bbox
                
                # Add padding
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.width, x + w + padding)
                y2 = min(img.height, y + h + padding)
                
                # Crop image
                cropped = img.crop((x1, y1, x2, y2))
                
                # Save cropped image
                cropped.save(output_path, "JPEG", quality=90, optimize=True)
                
            logger.info(f"Image cropped: {image_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Image cropping error: {str(e)}")
            return False

    @staticmethod
    def auto_orient_image(image_path: str, output_path: str = None) -> str:
        """
        Auto-orient image based on EXIF data
        
        Args:
            image_path: Input image path
            output_path: Output image path (if None, overwrites input)
            
        Returns:
            Path to oriented image
        """
        try:
            output_path = output_path or image_path
            
            with Image.open(image_path) as img:
                # Auto-orient based on EXIF
                img = ImageOps.exif_transpose(img)
                
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save oriented image
                img.save(output_path, "JPEG", quality=90, optimize=True)
                
            logger.info(f"Image oriented: {image_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Image orientation error: {str(e)}")
            return image_path

    @staticmethod
    def calculate_image_quality_score(image_path: str) -> float:
        """
        Calculate basic image quality score
        
        Args:
            image_path: Path to image file
            
        Returns:
            Quality score between 0 and 1
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                return 0.0
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate Laplacian variance (sharpness)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate brightness
            brightness = np.mean(gray)
            
            # Calculate contrast (standard deviation)
            contrast = np.std(gray)
            
            # Normalize scores
            sharpness_score = min(laplacian_var / 1000.0, 1.0)  # Normalize to 0-1
            brightness_score = 1.0 - abs(brightness - 128) / 128.0  # Optimal brightness around 128
            contrast_score = min(contrast / 128.0, 1.0)  # Normalize to 0-1
            
            # Weighted average
            quality_score = (sharpness_score * 0.4 + brightness_score * 0.3 + contrast_score * 0.3)
            
            return float(quality_score)
            
        except Exception as e:
            logger.error(f"Quality score calculation error: {str(e)}")
            return 0.0

    @staticmethod
    def create_thumbnail(image_path: str, 
                        output_path: str,
                        size: Tuple[int, int] = (150, 150)) -> bool:
        """
        Create thumbnail image
        
        Args:
            image_path: Input image path
            output_path: Output thumbnail path
            size: Thumbnail size
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB
                img = img.convert("RGB")
                
                # Create thumbnail
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save thumbnail
                img.save(output_path, "JPEG", quality=85, optimize=True)
                
            logger.info(f"Thumbnail created: {image_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Thumbnail creation error: {str(e)}")
            return False


# Convenience functions
def validate_image(image_path: str) -> bool:
    """Validate image file"""
    return ImageProcessor.validate_image(image_path)

def get_image_info(image_path: str) -> Dict:
    """Get image information"""
    return ImageProcessor.get_image_info(image_path)

def preprocess_image(image_path: str, **kwargs) -> np.ndarray:
    """Preprocess image for model input"""
    return ImageProcessor.preprocess_image(image_path, **kwargs)

def resize_image_if_needed(image_path: str, 
                          output_path: str = None,
                          max_size: Tuple[int, int] = None) -> str:
    """
    Resize image if it exceeds maximum dimensions
    
    Args:
        image_path: Input image path
        output_path: Output image path (if None, overwrites input)
        max_size: Maximum dimensions
        
    Returns:
        Path to resized image
    """
    try:
        output_path = output_path or image_path
        max_size = max_size or ImageProcessor.MAX_SIZE
        
        # Get image info
        img_info = get_image_info(image_path)
        
        # Check if resize is needed
        if (img_info.get('width', 0) > max_size[0] or 
            img_info.get('height', 0) > max_size[1]):
            
            success = ImageProcessor.resize_image(image_path, output_path, max_size)
            return output_path if success else image_path
        
        # No resize needed
        if output_path != image_path:
            import shutil
            shutil.copy2(image_path, output_path)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error in resize_image_if_needed: {str(e)}")
        return image_path

def process_uploaded_image(image_path: str, 
                          output_dir: str,
                          enhance: bool = True,
                          auto_orient: bool = True) -> Dict[str, str]:
    """
    Process uploaded image for wound analysis
    
    Args:
        image_path: Input image path
        output_dir: Output directory
        enhance: Whether to enhance the image
        auto_orient: Whether to auto-orient the image
        
    Returns:
        Dictionary with processed image paths
    """
    try:
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate filenames
        base_name = Path(image_path).stem
        processed_path = os.path.join(output_dir, f"{base_name}_processed.jpg")
        thumbnail_path = os.path.join(output_dir, f"{base_name}_thumb.jpg")
        
        # Auto-orient image
        current_path = image_path
        if auto_orient:
            oriented_path = os.path.join(output_dir, f"{base_name}_oriented.jpg")
            current_path = ImageProcessor.auto_orient_image(image_path, oriented_path)
        
        # Resize if needed
        resized_path = os.path.join(output_dir, f"{base_name}_resized.jpg")
        current_path = resize_image_if_needed(current_path, resized_path)
        
        # Enhance image
        if enhance:
            current_path = ImageProcessor.enhance_wound_image(current_path, processed_path)
        else:
            processed_path = current_path
        
        # Create thumbnail
        ImageProcessor.create_thumbnail(processed_path, thumbnail_path)
        
        # Calculate quality score
        quality_score = ImageProcessor.calculate_image_quality_score(processed_path)
        
        return {
            'original': image_path,
            'processed': processed_path,
            'thumbnail': thumbnail_path,
            'quality_score': quality_score
        }
        
    except Exception as e:
        logger.error(f"Image processing error: {str(e)}")
        return {'original': image_path, 'processed': image_path}
    
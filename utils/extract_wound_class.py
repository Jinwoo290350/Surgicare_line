"""
Wound classification using cached ONNX model
Optimized version with better error handling and performance monitoring
"""

import os
import time
import tempfile
import requests
import numpy as np
import onnxruntime as ort
from onnxruntime import OrtDevice
from onnxruntime.quantization import quantize_dynamic, QuantType
from PIL import Image
from torchvision import transforms
import logging
from typing import Dict, Tuple, Optional, List
from pathlib import Path
import hashlib

from .image_utils import validate_image, preprocess_image, get_image_info

logger = logging.getLogger(__name__)

class WoundClassifier:
    """
    Optimized wound classifier using ONNX runtime
    Features: caching, quantization, CUDA optimization, error handling
    """
    
    MODEL_URL = "https://huggingface.co/PogusTheWhisper/Surgicare-ALB-fold4-stage3/resolve/main/topdown_model_fold4_stage3_opset_20.onnx"
    
    CLASS_LABELS = {
        0: 'Abrasions',
        1: 'Bruises', 
        2: 'Burns',
        3: 'Cut',
        4: 'Normal'
    }
    
    CLASS_LABELS_TH = {
        0: 'แผลถลอก',
        1: 'รอยช้ำ',
        2: 'แผลไฟไหม้', 
        3: 'แผลบาด',
        4: 'ผิวหนังปกติ'
    }

    def __init__(self, 
                 cache_dir: Optional[str] = None,
                 use_fp16: bool = True,
                 device: Optional[str] = None,
                 enable_optimization: bool = True):
        """
        Initialize wound classifier
        
        Args:
            cache_dir: Directory for model caching
            use_fp16: Use FP16 quantization for CUDA
            device: Computing device ('cuda' or 'cpu')
            enable_optimization: Enable ONNX optimizations
        """
        self.cache_dir = cache_dir or os.getenv('MODEL_CACHE_DIR', tempfile.gettempdir())
        self.use_fp16 = use_fp16
        self.enable_optimization = enable_optimization
        
        # Create cache directory
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        # Model paths
        self.model_path = os.path.join(self.cache_dir, "wound_model_fp32.onnx")
        self.quant_path = os.path.join(self.cache_dir, "wound_model_fp16.onnx")
        
        # Device setup
        self.device = self._setup_device(device)
        
        # Performance metrics
        self.inference_times = []
        self.prediction_count = 0
        
        # Initialize model
        self._initialize_model()
        
        logger.info(f"WoundClassifier initialized on {self.device}")

    def _setup_device(self, device: Optional[str]) -> str:
        """Setup computing device"""
        if device:
            return device
            
        # Auto-detect best device
        providers = ort.get_available_providers()
        use_cuda = "CUDAExecutionProvider" in providers and os.getenv('USE_CUDA', 'True').lower() == 'true'
        
        selected_device = "cuda" if use_cuda else "cpu"
        logger.info(f"Available providers: {providers}")
        logger.info(f"Selected device: {selected_device}")
        
        return selected_device

    def _initialize_model(self):
        """Initialize ONNX model with optimizations"""
        try:
            # Download model if needed
            self._ensure_model_downloaded()
            
            # Get model path (quantized or original)
            model_path = self._get_model_path()
            
            # Create optimized session
            self.session = self._create_optimized_session(model_path)
            
            # Setup input/output
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Setup CUDA optimization
            self._setup_cuda_optimization()
            
            # Setup image transforms
            self._setup_transforms()
            
            logger.info("Model initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Model initialization failed: {str(e)}")
            raise

    def _ensure_model_downloaded(self):
        """Download model if not exists"""
        if os.path.exists(self.model_path):
            logger.info("Model already exists, skipping download")
            return
            
        logger.info("Downloading wound classification model...")
        
        try:
            timeout = int(os.getenv('MODEL_DOWNLOAD_TIMEOUT', 300))
            
            response = requests.get(self.MODEL_URL, stream=True, timeout=timeout)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(self.model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if downloaded_size % (10*1024*1024) == 0:  # Log every 10MB
                                logger.info(f"Download progress: {progress:.1f}%")
            
            # Verify downloaded file
            if os.path.getsize(self.model_path) < 1024:  # Less than 1KB is suspicious
                raise ValueError("Downloaded model file is too small")
                
            logger.info("Model download completed successfully")
            
        except Exception as e:
            # Cleanup partial download
            if os.path.exists(self.model_path):
                os.remove(self.model_path)
            logger.error(f"Model download failed: {str(e)}")
            raise

    def _get_model_path(self) -> str:
        """Get appropriate model path (quantized or original)"""
        if not self.use_fp16 or self.device != "cuda":
            return self.model_path
            
        # Create quantized model if needed
        if not os.path.exists(self.quant_path):
            logger.info("Creating FP16 quantized model...")
            try:
                quantize_dynamic(
                    self.model_path,
                    self.quant_path,
                    weight_type=QuantType.QFloat16
                )
                logger.info("FP16 quantization completed")
            except Exception as e:
                logger.warning(f"FP16 quantization failed: {str(e)}, using FP32")
                return self.model_path
        
        return self.quant_path

    def _create_optimized_session(self, model_path: str) -> ort.InferenceSession:
        """Create optimized ONNX inference session"""
        # Session options
        session_options = ort.SessionOptions()
        
        if self.enable_optimization:
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session_options.intra_op_num_threads = min(os.cpu_count(), 8)
            session_options.inter_op_num_threads = 1
            session_options.enable_mem_pattern = True
            session_options.enable_cpu_mem_arena = True
        
        session_options.log_severity_level = 3  # ERROR level
        
        # Provider setup
        providers, provider_options = self._get_providers()
        
        try:
            session = ort.InferenceSession(
                model_path,
                sess_options=session_options,
                providers=providers,
                provider_options=provider_options
            )
            
            logger.info(f"ONNX session created with providers: {session.get_providers()}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create ONNX session: {str(e)}")
            raise

    def _get_providers(self) -> Tuple[List[str], List[Dict]]:
        """Get ONNX execution providers and options"""
        if self.device == "cuda":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            provider_options = [
                {
                    "device_id": 0,
                    "cudnn_conv_algo_search": "EXHAUSTIVE",
                    "arena_extend_strategy": "kNextPowerOfTwo",
                    "do_copy_in_default_stream": True,
                },
                {}
            ]
        else:
            providers = ["CPUExecutionProvider"]
            provider_options = [{}]
            
        return providers, provider_options

    def _setup_cuda_optimization(self):
        """Setup CUDA-specific optimizations"""
        if self.device != "cuda":
            self.io_binding = None
            return
            
        try:
            # Get input shape
            input_shape = self.session.get_inputs()[0].shape
            shape = [1] + [dim if dim is not None else 224 for dim in input_shape[1:]]
            
            # Pre-allocate input buffer
            self._input_buffer = ort.OrtValue.ortvalue_from_numpy(
                np.zeros(shape, dtype=np.float32),
                OrtDevice("cuda", 0)
            )
            
            # Setup IO binding for zero-copy inference
            self.io_binding = self.session.io_binding()
            self.io_binding.bind_input(
                name=self.input_name,
                device_type="cuda",
                device_id=0,
                element_type=np.float32,
                shape=shape,
                buffer_ptr=self._input_buffer.data_ptr()
            )
            
            logger.info("CUDA optimization setup completed")
            
        except Exception as e:
            logger.warning(f"CUDA optimization failed: {str(e)}")
            self.io_binding = None

    def _setup_transforms(self):
        """Setup image preprocessing transforms"""
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def predict(self, image_path: str, return_probabilities: bool = True) -> Tuple[str, np.ndarray]:
        """
        Predict wound class from image
        
        Args:
            image_path: Path to image file
            return_probabilities: Whether to return class probabilities
            
        Returns:
            Tuple of (predicted_class, probabilities)
        """
        start_time = time.time()
        
        try:
            # Validate image
            if not validate_image(image_path):
                raise ValueError(f"Invalid image file: {image_path}")
            
            # Load and preprocess image
            image_tensor = self._preprocess_image(image_path)
            
            # Run inference
            probabilities = self._run_inference(image_tensor)
            
            # Get prediction
            predicted_idx = int(np.argmax(probabilities))
            predicted_class = self.CLASS_LABELS[predicted_idx]
            
            # Update metrics
            inference_time = time.time() - start_time
            self.inference_times.append(inference_time)
            self.prediction_count += 1
            
            logger.info(
                f"Prediction: {predicted_class} "
                f"(confidence: {probabilities.max():.3f}, "
                f"time: {inference_time:.3f}s)"
            )
            
            return predicted_class, probabilities if return_probabilities else probabilities.max()
            
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            raise

    def _preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image for model input"""
        try:
            image = Image.open(image_path).convert("RGB")
            tensor = self.transform(image).unsqueeze(0)
            return tensor.numpy()
            
        except Exception as e:
            logger.error(f"Image preprocessing error: {str(e)}")
            raise

    def _run_inference(self, image_tensor: np.ndarray) -> np.ndarray:
        """Run model inference"""
        try:
            if self.io_binding:
                # CUDA optimized inference
                np.copyto(self._input_buffer.numpy(), image_tensor)
                self.io_binding.bind_output(
                    name=self.output_name,
                    device_type="cuda",
                    device_id=0
                )
                self.session.run_with_iobinding(self.io_binding)
                output = self.io_binding.get_outputs()[0].numpy()
            else:
                # Standard inference
                output = self.session.run(
                    [self.output_name],
                    {self.input_name: image_tensor}
                )[0]
            
            # Apply softmax
            exp_output = np.exp(output - output.max(axis=1, keepdims=True))
            probabilities = exp_output / exp_output.sum(axis=1, keepdims=True)
            
            return probabilities[0]  # Return single prediction
            
        except Exception as e:
            logger.error(f"Inference error: {str(e)}")
            raise

    def get_class_probabilities(self, image_path: str, language: str = 'en') -> Dict[str, float]:
        """
        Get probabilities for all classes
        
        Args:
            image_path: Path to image file
            language: Language for class names ('en' or 'th')
            
        Returns:
            Dictionary mapping class names to probabilities
        """
        _, probabilities = self.predict(image_path)
        
        labels = self.CLASS_LABELS_TH if language == 'th' else self.CLASS_LABELS
        
        return {
            labels[idx]: float(prob)
            for idx, prob in enumerate(probabilities)
        }

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        if not self.inference_times:
            return {}
            
        times = np.array(self.inference_times)
        
        return {
            'total_predictions': self.prediction_count,
            'avg_inference_time': float(times.mean()),
            'min_inference_time': float(times.min()),
            'max_inference_time': float(times.max()),
            'std_inference_time': float(times.std())
        }

    def reset_stats(self):
        """Reset performance statistics"""
        self.inference_times = []
        self.prediction_count = 0

    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'io_binding') and self.io_binding:
                del self.io_binding
            if hasattr(self, '_input_buffer'):
                del self._input_buffer
            if hasattr(self, 'session'):
                del self.session
            logger.info("Wound classifier cleanup completed")
        except Exception as e:
            logger.warning(f"Cleanup warning: {str(e)}")

    def __del__(self):
        """Destructor"""
        self.cleanup()


# Singleton instance for global use
_classifier_instance = None

def get_wound_classifier(**kwargs) -> WoundClassifier:
    """Get singleton wound classifier instance"""
    global _classifier_instance
    
    if _classifier_instance is None:
        _classifier_instance = WoundClassifier(**kwargs)
    
    return _classifier_instance

def classify_wound_image(image_path: str, language: str = 'en') -> Dict:
    """
    Convenience function to classify wound image
    
    Args:
        image_path: Path to image file
        language: Language for results ('en' or 'th')
        
    Returns:
        Classification results dictionary
    """
    classifier = get_wound_classifier()
    
    predicted_class, probabilities = classifier.predict(image_path)
    class_probabilities = classifier.get_class_probabilities(image_path, language)
    
    return {
        'predicted_class': predicted_class,
        'confidence': float(probabilities.max()),
        'probabilities': class_probabilities,
        'language': language
    }

"""
Feature extraction using BiomedVLP-BioViL-T for wound descriptions
Optimized version with caching and better language support
"""

import torch
from PIL import Image
from transformers import AutoTokenizer, AutoModel
from typing import List, Dict, Tuple, Optional
import warnings
from transformers.utils import logging as transformers_logging
import logging
import numpy as np
import os
from functools import lru_cache
import hashlib
import pickle
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")
transformers_logging.set_verbosity_error()

logger = logging.getLogger(__name__)

class WoundFeatureExtractor:
    """
    Enhanced wound feature extractor using BiomedVLP-BioViL-T
    Features: caching, multilingual support, optimized inference
    """

    MODEL_NAME = "microsoft/BiomedVLP-BioViL-T"
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.3))
    MAX_FEATURES = int(os.getenv('MAX_FEATURES', 10))

    # English feature descriptions
    CLASS_FEATURES_EN = {
        'Abrasions': [
            "Superficial wound limited to the epidermis",
            "Redness and raw appearance typical of abrasions",
            "Minimal exudate with intact surrounding skin",
            "Scab formation is present as part of healing",
            "The wound surface appears scraped with irregular borders",
            "There is mild serous fluid visible on the wound",
            "No signs of necrosis or infection are observed",
            "Periwound skin shows mild inflammation and dryness",
            "Wound area is shallow and does not extend into dermis",
            "Granulation tissue is forming on the wound bed",
            "Surface bleeding has stopped with clot formation",
            "Debris and dirt particles may be embedded in surface"
        ],
        'Bruises': [
            "Bluish-purple discoloration of the skin",
            "No open wound or tissue loss is observed",
            "Tenderness and swelling without active bleeding",
            "Discoloration fades from purple to yellow over time",
            "Skin remains intact with localized subdermal bleeding",
            "The area is soft to the touch but non-blanching",
            "Swelling is present without any exudate or odor",
            "No signs of epidermal disruption or trauma",
            "Periwound skin is normal in texture but discolored",
            "Bruised area is tender and warm without signs of infection",
            "Hematoma formation visible under the skin",
            "Color changes progress through healing spectrum"
        ],
        'Burns': [
            "Blister formation consistent with second-degree burns",
            "Charred or leathery skin appearance indicating full-thickness burn",
            "Redness and swelling in the burn area",
            "Burn site has dry, cracked skin with sloughing",
            "Peeling skin with visible dermal exposure",
            "The wound emits a faint odor typical of burn injuries",
            "No significant bleeding, but eschar is forming",
            "Surrounding skin is erythematous and painful",
            "Burn depth extends into subcutaneous layers",
            "Burn margins are irregular with variable tissue response",
            "Fluid-filled blisters present on wound surface",
            "Tissue necrosis visible in deeper burn areas"
        ],
        'Cut': [
            "Well-defined linear wound with clean edges",
            "Bleeding is present, consistent with a fresh cut",
            "Exposed tissue at the wound site",
            "The wound edges are approximated with signs of healing",
            "There is minor clotting along the wound bed",
            "Cut extends partially through the dermis",
            "Moderate bleeding occurred but is now controlled",
            "No signs of infection or necrosis around the laceration",
            "Wound bed is moist with early granulation tissue",
            "Cut was likely caused by a sharp object",
            "Wound edges are clean and well-demarcated",
            "Depth varies along the length of the laceration"
        ],
        'Normal': [
            "Skin appears intact with no visible injury",
            "There is no redness, swelling, or open wound",
            "Normal skin tone and texture with no exudate",
            "The area is dry and free of abnormalities",
            "No signs of trauma, bruising, or inflammation",
            "Skin is smooth with no lesions or discoloration",
            "Temperature and texture are consistent with healthy tissue",
            "No maceration or irritation present",
            "Healthy skin integrity is maintained",
            "No pain, odor, or drainage reported in the area",
            "Natural skin color and pigmentation visible",
            "Skin elasticity and turgor appear normal"
        ]
    }
    
    # Thai feature descriptions
    CLASS_FEATURES_TH = {
        'Abrasions': [
            "แผลถลอกอยู่เพียงชั้นหนังกำพร้าเท่านั้น",
            "มีรอยแดงและลักษณะเหมือนถลอกที่พบได้ทั่วไป",
            "มีของเหลวเล็กน้อยและผิวหนังรอบแผลยังคงสมบูรณ์",
            "พบสะเก็ดแผลซึ่งเป็นส่วนหนึ่งของกระบวนการหาย",
            "พื้นผิวแผลดูเหมือนถูกขูดขีด ขอบแผลไม่เรียบ",
            "มีของเหลวใสเล็กน้อยปรากฏบนแผล",
            "ไม่พบสัญญาณของเนื้อตายหรือการติดเชื้อ",
            "ผิวหนังรอบแผลมีการอักเสบเล็กน้อยและแห้ง",
            "แผลมีความตื้นและไม่ลึกถึงชั้นหนังแท้",
            "พบเนื้อเยื่อแกรนูลกำลังก่อตัวในบริเวณแผล",
            "เลือดออกบนพื้นผิวหยุดแล้วและมีลิ่มเลือด",
            "อาจพบเศษสิ่งสกปรกติดอยู่บนพื้นผิวแผล"
        ],
        'Bruises': [
            "มีรอยช้ำสีน้ำเงินอมม่วงบนผิวหนัง",
            "ไม่พบแผลเปิดหรือการสูญเสียเนื้อเยื่อ",
            "บริเวณที่ช้ำมีอาการบวมและเจ็บแต่ไม่มีเลือดออก",
            "สีของรอยช้ำเปลี่ยนจากม่วงเป็นเหลืองตามเวลา",
            "ผิวหนังยังคงสมบูรณ์แต่มีเลือดออกใต้ผิวหนังเฉพาะจุด",
            "บริเวณนี้นิ่มเมื่อสัมผัสแต่ไม่ซีดลงเมื่อกด",
            "มีอาการบวมแต่ไม่มีของเหลวหรือกลิ่นผิดปกติ",
            "ไม่พบร่องรอยของการฉีกขาดหรือบาดเจ็บภายนอก",
            "ผิวหนังรอบแผลมีสีผิดปกติแต่ลักษณะพื้นผิวปกติ",
            "บริเวณที่ช้ำรู้สึกเจ็บและอุ่นโดยไม่มีสัญญาณของการติดเชื้อ",
            "เห็นการก่อตัวของก้อนเลือดใต้ผิวหนัง",
            "การเปลี่ยนสีดำเนินไปตามขั้นตอนการหาย"
        ],
        'Burns': [
            "พบบวมพองซึ่งสอดคล้องกับแผลไฟไหม้ระดับที่สอง",
            "ผิวหนังไหม้ดำหรือแข็งคล้ายหนัง บ่งชี้แผลไหม้ลึกถึงชั้นผิวหนังทั้งหมด",
            "มีรอยแดงและบวมในบริเวณที่ไหม้",
            "บริเวณแผลไหม้มีผิวแห้ง แตก และลอกออก",
            "ผิวหนังลอกออกและเห็นชั้นผิวหนังด้านใน",
            "แผลมีกลิ่นจางๆ ซึ่งพบได้ในแผลไฟไหม้",
            "ไม่มีเลือดออกมาก แต่มีสะเก็ดแผลเริ่มก่อตัว",
            "ผิวหนังรอบแผลมีรอยแดงและเจ็บปวด",
            "ความลึกของแผลไหม้ลามถึงชั้นใต้ผิวหนัง",
            "ขอบแผลไหม้ไม่เรียบและมีปฏิกิริยาของเนื้อเยื่อแตกต่างกัน",
            "พบพุพองที่มีน้ำใสบนผิวหนังที่ไหม้",
            "เห็นเนื้อเยื่อตายในบริเวณที่ไหม้ลึก"
        ],
        'Cut': [
            "แผลมีลักษณะเป็นเส้นตรง ขอบแผลชัดเจน",
            "มีเลือดออก สอดคล้องกับแผลที่เพิ่งเกิดใหม่",
            "เห็นเนื้อเยื่อภายในบริเวณแผล",
            "ขอบแผลเริ่มติดกัน บ่งบอกกระบวนการสมานแผล",
            "มีการแข็งตัวของเลือดเล็กน้อยในแผล",
            "แผลลึกลงถึงชั้นหนังแท้บางส่วน",
            "เคยมีเลือดออกปานกลาง แต่ขณะนี้ควบคุมได้แล้ว",
            "ไม่พบการติดเชื้อหรือเนื้อตายรอบแผล",
            "พื้นแผลมีความชื้น และเริ่มมีเนื้อเยื่อแกรนูล",
            "แผลดูเหมือนเกิดจากของมีคม",
            "ขอบแผลสะอาดและมีเส้นแบ่งชัดเจน",
            "ความลึกแตกต่างกันไปตามความยาวของแผล"
        ],
        'Normal': [
            "ผิวหนังดูปกติและไม่มีบาดแผลให้เห็น",
            "ไม่พบรอยแดง บวม หรือแผลเปิด",
            "สีผิวและลักษณะพื้นผิวปกติ ไม่มีของเหลวผิดปกติ",
            "บริเวณนี้แห้งและไม่พบความผิดปกติใดๆ",
            "ไม่พบร่องรอยของการบาดเจ็บ รอยช้ำ หรือการอักเสบ",
            "ผิวเรียบ ไม่มีแผลหรือจุดผิดปกติ",
            "อุณหภูมิและลักษณะผิวสอดคล้องกับผิวหนังปกติ",
            "ไม่พบการชื้นแฉะหรือการระคายเคืองบริเวณนี้",
            "โครงสร้างของผิวหนังยังคงแข็งแรงและสมบูรณ์",
            "ไม่พบอาการปวด กลิ่น หรือของเหลวใดๆ จากบริเวณนี้",
            "เห็นสีผิวและการแต่งสีตามธรรมชาติ",
            "ความยืดหยุ่นและความตึงของผิวหนังดูปกติ"
        ]
    }

    def __init__(self, 
                 device: Optional[str] = None,
                 cache_dir: Optional[str] = None,
                 enable_caching: bool = True):
        """
        Initialize wound feature extractor
        
        Args:
            device: Computing device ('cuda' or 'cpu')
            cache_dir: Directory for feature caching
            enable_caching: Enable feature caching
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_dir = cache_dir or os.getenv('MODEL_CACHE_DIR', Path.home() / '.cache' / 'wound_features')
        self.enable_caching = enable_caching
        
        # Create cache directory
        if self.enable_caching:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize model
        self._initialize_model()
        
        logger.info(f"WoundFeatureExtractor initialized on {self.device}")

    def _initialize_model(self):
        """Initialize the BiomedVLP model"""
        try:
            logger.info(f"Loading model: {self.MODEL_NAME}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.MODEL_NAME, 
                trust_remote_code=True,
                cache_dir=self.cache_dir if self.enable_caching else None
            )
            
            # Load model
            self.model = AutoModel.from_pretrained(
                self.MODEL_NAME, 
                trust_remote_code=True,
                cache_dir=self.cache_dir if self.enable_caching else None
            )
            
            # Move to device and set to eval mode
            self.model.eval().to(self.device)
            
            logger.info("BiomedVLP model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize model: {str(e)}")
            raise

    @lru_cache(maxsize=1000)
    def _get_cache_key(self, wound_class: str, lang: str) -> str:
        """Generate cache key for feature embeddings"""
        features_str = str(sorted(self._get_class_features(wound_class, lang)))
        return hashlib.md5(features_str.encode()).hexdigest()

    def _get_class_features(self, wound_class: str, lang: str) -> List[str]:
        """Get feature descriptions for a wound class"""
        if lang == 'th':
            return self.CLASS_FEATURES_TH.get(wound_class, [])
        else:
            return self.CLASS_FEATURES_EN.get(wound_class, [])

    def _load_cached_embeddings(self, cache_key: str) -> Optional[torch.Tensor]:
        """Load cached embeddings"""
        if not self.enable_caching:
            return None
            
        cache_file = Path(self.cache_dir) / f"{cache_key}.pkl"
        
        try:
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached embeddings: {str(e)}")
        
        return None

    def _save_cached_embeddings(self, cache_key: str, embeddings: torch.Tensor):
        """Save embeddings to cache"""
        if not self.enable_caching:
            return
            
        cache_file = Path(self.cache_dir) / f"{cache_key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(embeddings, f)
        except Exception as e:
            logger.warning(f"Failed to save cached embeddings: {str(e)}")

    def _encode_text(self, prompts: List[str]) -> torch.Tensor:
        """Tokenize and encode text prompts"""
        try:
            with torch.no_grad():
                # Tokenize
                tokens = self.tokenizer.batch_encode_plus(
                    batch_text_or_text_pairs=prompts,
                    add_special_tokens=True,
                    padding='longest',
                    return_tensors='pt',
                    truncation=True,
                    max_length=512
                ).to(self.device)

                # Get embeddings
                text_embeds = self.model.get_projected_text_embeddings(
                    input_ids=tokens.input_ids,
                    attention_mask=tokens.attention_mask
                )
                
                # Normalize embeddings
                return text_embeds / text_embeds.norm(dim=-1, keepdim=True)
                
        except Exception as e:
            logger.error(f"Text encoding error: {str(e)}")
            raise

    def extract_features(self,
                        image_path: str,
                        wound_class: str,
                        top_k: int = None,
                        lang: str = 'en') -> List[Tuple[str, float]]:
        """
        Extract top wound features based on similarity
        
        Args:
            image_path: Path to image (currently not used for image encoding)
            wound_class: Predicted wound class
            top_k: Number of top features to return
            lang: Language for features ('en' or 'th')
            
        Returns:
            List of (feature_description, similarity_score) tuples
        """
        top_k = top_k or self.MAX_FEATURES
        
        try:
            # Get feature descriptions
            features = self._get_class_features(wound_class, 'en')  # Always use English for similarity
            
            if not features:
                logger.warning(f"No features available for class '{wound_class}'")
                return []
            
            # Check cache
            cache_key = self._get_cache_key(wound_class, 'en')
            text_embeds = self._load_cached_embeddings(cache_key)
            
            if text_embeds is None:
                # Encode features
                text_embeds = self._encode_text(features)
                # Cache embeddings
                self._save_cached_embeddings(cache_key, text_embeds)
            else:
                text_embeds = text_embeds.to(self.device)
            
            # Calculate similarity matrix (using first feature as reference)
            similarities = torch.mm(text_embeds, text_embeds.t())
            ref_similarities = similarities[0]
            
            # Create results with indices and scores
            results = [
                (i, features[i], ref_similarities[i].item()) 
                for i in range(len(features))
            ]
            
            # Filter by threshold and sort by similarity
            filtered_results = [
                (idx, feat, score) for idx, feat, score in results 
                if score >= self.SIMILARITY_THRESHOLD
            ]
            
            sorted_results = sorted(filtered_results, key=lambda x: x[2], reverse=True)[:top_k]
            
            # Convert to target language if needed
            if lang == 'th':
                th_features = self._get_class_features(wound_class, 'th')
                if th_features and len(th_features) >= len(features):
                    return [(th_features[idx], score) for idx, _, score in sorted_results]
            
            # Return English features
            return [(feat, score) for _, feat, score in sorted_results]
            
        except Exception as e:
            logger.error(f"Feature extraction error: {str(e)}")
            return []

    def get_all_features(self, lang: str = 'en') -> Dict[str, List[str]]:
        """
        Get all feature descriptions for all classes
        
        Args:
            lang: Language for features ('en' or 'th')
            
        Returns:
            Dictionary mapping class names to feature lists
        """
        if lang == 'th':
            return self.CLASS_FEATURES_TH.copy()
        else:
            return self.CLASS_FEATURES_EN.copy()

    def get_feature_embedding(self, feature_text: str) -> torch.Tensor:
        """
        Get embedding for a single feature text
        
        Args:
            feature_text: Text to encode
            
        Returns:
            Normalized text embedding
        """
        return self._encode_text([feature_text])[0]

    def compare_features(self, 
                        feature1: str, 
                        feature2: str) -> float:
        """
        Compare similarity between two feature descriptions
        
        Args:
            feature1: First feature description
            feature2: Second feature description
            
        Returns:
            Similarity score (0-1)
        """
        try:
            embeds = self._encode_text([feature1, feature2])
            similarity = torch.cosine_similarity(embeds[0:1], embeds[1:2])
            return float(similarity.item())
            
        except Exception as e:
            logger.error(f"Feature comparison error: {str(e)}")
            return 0.0

    def get_feature_stats(self) -> Dict[str, int]:
        """Get statistics about available features"""
        stats = {}
        
        for lang in ['en', 'th']:
            features = self.get_all_features(lang)
            stats[f'total_classes_{lang}'] = len(features)
            stats[f'total_features_{lang}'] = sum(len(feats) for feats in features.values())
            stats[f'avg_features_per_class_{lang}'] = stats[f'total_features_{lang}'] // len(features)
        
        return stats

    def clear_cache(self):
        """Clear feature embedding cache"""
        if not self.enable_caching:
            return
            
        try:
            cache_dir = Path(self.cache_dir)
            if cache_dir.exists():
                for cache_file in cache_dir.glob("*.pkl"):
                    cache_file.unlink()
                logger.info("Feature cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear cache: {str(e)}")

    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'model'):
                del self.model
            if hasattr(self, 'tokenizer'):
                del self.tokenizer
            logger.info("WoundFeatureExtractor cleanup completed")
        except Exception as e:
            logger.warning(f"Cleanup warning: {str(e)}")

    def __del__(self):
        """Destructor"""
        self.cleanup()


# Singleton instance for global use
_feature_extractor_instance = None

def get_feature_extractor(**kwargs) -> WoundFeatureExtractor:
    """Get singleton feature extractor instance"""
    global _feature_extractor_instance
    
    if _feature_extractor_instance is None:
        _feature_extractor_instance = WoundFeatureExtractor(**kwargs)
    
    return _feature_extractor_instance

def extract_wound_features(image_path: str, 
                          wound_class: str, 
                          top_k: int = 5,
                          lang: str = 'en') -> List[Tuple[str, float]]:
    """
    Convenience function to extract wound features
    
    Args:
        image_path: Path to wound image
        wound_class: Predicted wound class
        top_k: Number of top features to return
        lang: Language for features ('en' or 'th')
        
    Returns:
        List of (feature_description, similarity_score) tuples
    """
    extractor = get_feature_extractor()
    return extractor.extract_features(image_path, wound_class, top_k, lang)

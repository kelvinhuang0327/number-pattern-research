"""
Phase 65: Meta-Ensemble 2.0 (GBM Stacker)
LightGBM-based Meta-Learner for Power Lotto
Learns conditional correlations between sub-models based on Regime and Zonal features.
"""

import numpy as np
import lightgbm as lgb
import pickle
import os
import logging
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)


class GBMStacker:
    """
    Gradient Boosting Meta-Learner for Number Ranking
    Combines sub-model predictions with contextual features (Regime, Zonal Momentum)
    """
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path or 'lottery_api/data/stacker_v2.pkl'
        self.model: lgb.LGBMClassifier = None
        self.feature_names: List[str] = []
        self._load_model()
    
    def _load_model(self):
        """Load pre-trained model if available"""
        if self.model_path and os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    saved = pickle.load(f)
                    self.model = saved['model']
                    self.feature_names = saved['feature_names']
                logger.info(f"✅ GBM Stacker loaded from {self.model_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load GBM Stacker: {e}")
                self.model = None
    
    def save_model(self):
        """Save trained model"""
        if self.model:
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_names': self.feature_names
                }, f)
            logger.info(f"💾 GBM Stacker saved to {self.model_path}")
    
    def prepare_features(self, 
                        sub_model_scores: Dict[str, Dict[int, float]],
                        zonal_momentum: Dict[int, float],
                        zonal_entropy: Dict[int, float],
                        regime: str,
                        max_num: int = 38) -> np.ndarray:
        """
        Prepare feature matrix for all numbers (1 to max_num).
        
        Args:
            sub_model_scores: {'fourier': {1: 0.5, ...}, 'gnn': {...}, ...}
            zonal_momentum: {0: 1.15, 1: 1.0, ...} (Zone index -> momentum)
            zonal_entropy: {0: 0.3, 1: 0.5, ...} (Zone index -> entropy)
            regime: 'ORDER', 'CHAOS', or 'TRANSITION'
            max_num: Max number in the lottery (38 for Power Lotto)
        
        Returns:
            np.ndarray of shape (max_num, n_features)
        """
        zone_size = max_num // 5
        regime_map = {'ORDER': 0, 'CHAOS': 1, 'TRANSITION': 2}
        regime_idx = regime_map.get(regime, 1)
        
        features = []
        for n in range(1, max_num + 1):
            zone = min((n - 1) // zone_size, 4)
            
            row = []
            # Sub-model scores
            for model_name in sorted(sub_model_scores.keys()):
                row.append(sub_model_scores[model_name].get(n, 0.0))
            
            # Zonal features
            row.append(zonal_momentum.get(zone, 1.0))
            row.append(zonal_entropy.get(zone, 0.5))
            
            # Regime one-hot
            row.extend([1.0 if i == regime_idx else 0.0 for i in range(3)])
            
            # Number-level features
            row.append(n / max_num)  # Normalized position
            row.append(zone / 4.0)   # Normalized zone
            
            features.append(row)
        
        return np.array(features, dtype=np.float32)
    
    def train(self, 
              train_data: List[Tuple[Dict[str, Dict[int, float]], Dict[int, float], Dict[int, float], str, List[int], int]],
              params: Dict[str, Any] = None):
        """
        Train the GBM Meta-Learner.
        
        Args:
            train_data: List of (sub_model_scores, zonal_momentum, zonal_entropy, regime, actual_numbers, max_num)
        """
        X_all = []
        y_all = []
        
        for sub_scores, z_mom, z_ent, regime, actual, max_num in train_data:
            X = self.prepare_features(sub_scores, z_mom, z_ent, regime, max_num)
            y = np.zeros(max_num, dtype=np.float32)
            for n in actual:
                if 1 <= n <= max_num:
                    y[n - 1] = 1.0
            
            X_all.append(X)
            y_all.append(y)
        
        X_train = np.vstack(X_all)
        y_train = np.concatenate(y_all)
        
        # Define feature names
        model_names = sorted(train_data[0][0].keys())
        self.feature_names = (
            model_names + 
            ['zonal_momentum', 'zonal_entropy'] +
            ['regime_order', 'regime_chaos', 'regime_trans'] +
            ['norm_pos', 'norm_zone']
        )
        
        default_params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'n_estimators': 200,
            'class_weight': 'balanced'  # Handle imbalanced labels
        }
        if params:
            default_params.update(params)
        
        self.model = lgb.LGBMClassifier(**default_params)
        self.model.fit(X_train, y_train)
        
        logger.info(f"🎯 GBM Stacker trained on {len(X_train)} samples")
        self.save_model()
    
    def predict_scores(self,
                      sub_model_scores: Dict[str, Dict[int, float]],
                      zonal_momentum: Dict[int, float],
                      zonal_entropy: Dict[int, float],
                      regime: str,
                      max_num: int = 38) -> Dict[int, float]:
        """
        Predict refined probability scores for all numbers.
        
        Returns:
            Dict[int, float]: {1: 0.85, 2: 0.12, ...}
        """
        if self.model is None:
            logger.warning("⚠️ GBM Stacker not trained, returning raw average")
            # Fallback: average of sub-models
            avg_scores = {}
            for n in range(1, max_num + 1):
                avg_scores[n] = np.mean([
                    sub_model_scores[m].get(n, 0.0) 
                    for m in sub_model_scores
                ])
            return avg_scores
        
        X = self.prepare_features(sub_model_scores, zonal_momentum, zonal_entropy, regime, max_num)
        probs = self.model.predict_proba(X)[:, 1]
        
        return {i + 1: float(probs[i]) for i in range(max_num)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from trained model"""
        if self.model is None:
            return {}
        
        importance = self.model.feature_importances_
        return {name: float(imp) for name, imp in zip(self.feature_names, importance)}

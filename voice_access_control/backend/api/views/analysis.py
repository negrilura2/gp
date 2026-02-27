import os
import glob
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..view_utils import IsAdminUser

class EmbeddingImageView(APIView):
    """
    Get the latest embedding visualization image.
    """
    # permission_classes = [IsAdminUser] # Optional: strictly require admin

    def get(self, request):
        reports_dir = settings.REPORTS_DIR
        embedding_plots_dir = os.path.join(reports_dir, "plots", "embedding")
        
        if not os.path.exists(embedding_plots_dir):
            return Response({"error": "No embedding plots directory found"}, status=status.HTTP_404_NOT_FOUND)

        method = request.query_params.get("method", "tsne") # tsne or pca
        feature_type = request.query_params.get("feature_type", "") 
        score_norm = request.query_params.get("score_norm", "none") # none, tnorm, znorm, snorm
        
        # New pattern: {method}_{feature_type}_{score_norm}_*.png
        # If feature_type is provided, we can be more specific.
        # But we need to be flexible as feature_type might not always be known by frontend.
        
        # Construct glob pattern based on available params
        # plot_embedding.py format: f"{method}_{feature_type}_{score_norm}_{model_name}.png"
        
        # Start with method
        pattern_parts = [method]
        
        # Add feature_type wildcard if not provided, else specific type
        if feature_type:
            pattern_parts.append(feature_type)
        else:
            pattern_parts.append("*")
            
        # Add score_norm
        pattern_parts.append(score_norm)
        
        # Add model_name wildcard
        pattern_parts.append("*.png")
        
        pattern = "_".join(pattern_parts)
        # Example: tsne_*_znorm_*.png or tsne_mfcc_delta_none_*.png
            
        search_path = os.path.join(embedding_plots_dir, pattern)
        files = glob.glob(search_path)
        
        if not files:
            # Fallback 1: Try without score_norm (legacy files might not have it)
            # Legacy format: {method}_{feature_type}_{model_name}.png (no score_norm part)
            # This is tricky because glob matching is simple.
            # Let's try to find ANY file matching method and feature_type, and sort by time.
            fallback_pattern = f"{method}_*.png"
            if feature_type:
                fallback_pattern = f"{method}_{feature_type}_*.png"
            
            fallback_files = glob.glob(os.path.join(embedding_plots_dir, fallback_pattern))
            if fallback_files:
                files = fallback_files
            else:
                 return Response({"error": "No embedding images found"}, status=status.HTTP_404_NOT_FOUND)

        # Sort by modification time, newest first
        files.sort(key=os.path.getmtime, reverse=True)
        latest_file = files[0]
        
        try:
            f = open(latest_file, "rb")
            return FileResponse(f, content_type="image/png")
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from flask import Blueprint, render_template, make_response
import logging

logger = logging.getLogger(__name__)

views_bp = Blue# print('views', __name__)

@views_bp.route('/privacy')
def privacy_policy():
    """Render the privacy policy page. This route is publicly accessible."""
    logger.info("Privacy policy page accessed")

    # Render the template
    response = make_response(render_template('privacy.html'))

    # Add headers to ensure proper caching and content type
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=300'  # Cache for 5 minutes
    response.headers['X-Frame-Options'] = 'DENY'  # Prevent clickjacking

    logger.info("Privacy policy response prepared with headers")
    return response
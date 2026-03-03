from flask import Blueprint, request, jsonify, send_file, current_app
import os
import uuid
import logging
from .filters.fetch_sites import fetch_sites
from .filters.filter_sites import apply_filters
from .emails.fetch_emails import fetch_emails_from_csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), '../output')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@main.route('/api/fetch-sites', methods=['POST'])
def fetch_sites_route():
    """Fetch websites based on search criteria."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = ['country', 'city', 'keyword']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        # Get parameters
        country = data.get('country')
        city = data.get('city')
        keyword = data.get('keyword')
        count = int(data.get('count', 10))

        # Validate count
        if count < 1 or count > 1000:
            return jsonify({"error": "Count must be between 1 and 1000"}), 400

        # Generate unique output filename
        output_file = os.path.join(current_app.config['OUTPUT_FOLDER'], f'sites_{uuid.uuid4().hex}.csv')
        
        # Fetch sites
        fetch_sites(keyword, country, city, count, output_file)

        return jsonify({
            "status": "success",
            "message": "Sites fetched successfully",
            "file": output_file
        })

    except Exception as e:
        logger.error(f"Error in fetch_sites_route: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main.route('/api/filter-sites', methods=['POST'])
def filter_sites_route():
    """Apply filters to uploaded CSV file."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        # Validate file extension
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are allowed"}), 400

        # Get filters
        filters = request.form.getlist('filters')
        if not filters:
            return jsonify({"error": "No filters selected"}), 400

        # Save uploaded file
        filename = f"{uuid.uuid4().hex}.csv"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Generate output filename
        output_file = os.path.join(current_app.config['OUTPUT_FOLDER'], f'filtered_{uuid.uuid4().hex}.csv')

        # Apply filters
        apply_filters(filepath, filters, output_file)

        # Clean up uploaded file
        try:
            os.remove(filepath)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {filepath}: {str(e)}")

        return jsonify({
            "status": "success",
            "message": "Filters applied successfully",
            "file": output_file
        })

    except Exception as e:
        logger.error(f"Error in filter_sites_route: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main.route('/api/download', methods=['GET'])
def download_file():
    """Download a processed file."""
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({"error": "No file path provided"}), 400

        # Validate file path is within allowed directories
        allowed_dirs = [
            current_app.config['OUTPUT_FOLDER'],
            current_app.config['UPLOAD_FOLDER']
        ]
        
        if not any(path.startswith(dir) for dir in allowed_dirs):
            return jsonify({"error": "Invalid file path"}), 403

        if not os.path.exists(path):
            return jsonify({"error": "File not found"}), 404

        return send_file(
            path,
            as_attachment=True,
            download_name=os.path.basename(path)
        )

    except Exception as e:
        logger.error(f"Error in download_file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main.route('/api/fetch-emails', methods=['POST'])
def fetch_emails_route():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Only CSV files are allowed"}), 400

    upload_folder = current_app.config['UPLOAD_FOLDER']
    output_folder = current_app.config['OUTPUT_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    input_path = os.path.join(upload_folder, f"{uuid.uuid4().hex}.csv")
    output_path = os.path.join(output_folder, f"emails_{uuid.uuid4().hex}.csv")
    file.save(input_path)

    # Run email extraction
    fetch_emails_from_csv(input_path, output_path, max_workers=5)

    # Optionally, clean up input file
    try:
        os.remove(input_path)
    except Exception:
        pass

    return jsonify({"status": "success", "file": output_path})

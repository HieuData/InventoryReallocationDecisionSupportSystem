from flask import Blueprint, request, jsonify, session
import pandas as pd
import os
import sys
sys.path.insert(0, '.')
from core.data_processor import (
    load_single_file, concat_files,
    calculate_broken_index_all, create_store_profiles
)
from config.settings import UPLOAD_FOLDER

bp = Blueprint('upload', __name__, url_prefix='/api/upload')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@bp.route('/files', methods=['POST'])
def upload_files():
    """Upload và xử lý CSV files"""
    try:
        store_files = request.files.getlist('store_files')
        warehouse_files = request.files.getlist('warehouse_files')
        season = request.form.get('season', 'false') == 'true'

        print(f"Received files - Store: {len(store_files)}, Warehouse: {len(warehouse_files)}")

        if not store_files or not warehouse_files:
            return jsonify({'error': 'Missing files'}), 400

        # Check if files have filenames
        if not any(f.filename for f in store_files) or not any(f.filename for f in warehouse_files):
            return jsonify({'error': 'No files selected'}), 400

        # Lưu files và load data
        store_paths = []
        for f in store_files:
            if f.filename and f.filename.endswith('.csv'):
                path = os.path.join(UPLOAD_FOLDER, f.filename)
                f.save(path)
                store_paths.append(path)
                print(f"Saved store file: {path}")

        warehouse_paths = []
        for f in warehouse_files:
            if f.filename and f.filename.endswith('.csv'):
                path = os.path.join(UPLOAD_FOLDER, f.filename)
                f.save(path)
                warehouse_paths.append(path)
                print(f"Saved warehouse file: {path}")

        if not store_paths or not warehouse_paths:
            return jsonify({'error': 'No valid CSV files uploaded'}), 400

        # Load và xử lý data
        print("Loading files...")
        store_dfs = [load_single_file(f, 'store', season=season) for f in store_paths]
        wh_dfs = [load_single_file(f, 'warehouse') for f in warehouse_paths]

        df_stores = concat_files(store_dfs)
        df_warehouse = concat_files(wh_dfs)
        print(f"Loaded - Stores: {len(df_stores)} rows, Warehouse: {len(df_warehouse)} rows")

        # Tính broken index và profiles
        print("Calculating broken index...")
        df_broken = calculate_broken_index_all(df_stores, df_warehouse)
        print("Creating store profiles...")
        store_profiles = create_store_profiles(df_stores, df_broken)

        # Lưu vào session
        print("Saving to session...")
        session.clear()  # Clear old session data first
        session['df_stores'] = df_stores.to_dict('records')
        session['df_warehouse'] = df_warehouse.to_dict('records')
        session['df_broken'] = df_broken.to_dict('records')
        session['store_profiles'] = store_profiles.to_dict('records')
        session['store_files'] = store_paths
        session['warehouse_files'] = warehouse_paths
        session['optimization_done'] = False
        session.modified = True  # Mark session as modified

        print("Session saved successfully")
        print(f"Session keys: {list(session.keys())}")

        return jsonify({
            'status': 'success',
            'message': 'Files uploaded and processed',
            'stores': len(df_stores),
            'warehouse_items': len(df_warehouse),
            'broken_combinations': len(df_broken)
        })

    except Exception as e:
        print(f"Error in upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/status')
def status():
    """Kiểm tra trạng thái data đã load chưa"""
    print(f"Checking status - Session keys: {list(session.keys())}")

    has_data = all([
        'df_stores' in session,
        'df_warehouse' in session,
        'df_broken' in session,
        'store_profiles' in session
    ])

    print(f"Has data: {has_data}")
    print(f"df_stores in session: {'df_stores' in session}")
    print(f"df_warehouse in session: {'df_warehouse' in session}")
    print(f"df_broken in session: {'df_broken' in session}")
    print(f"store_profiles in session: {'store_profiles' in session}")

    return jsonify({
        'has_data': has_data,
        'optimization_done': session.get('optimization_done', False),
        'session_keys': list(session.keys())
    })

@bp.route('/clear', methods=['POST'])
def clear():
    """Clear uploaded files, session data, output files and session storage"""
    try:
        import glob
        import shutil

        deleted_items = []

        # Clear session
        session.clear()
        print("Session cleared")

        # Delete uploaded files in uploads/
        uploaded_files = glob.glob(os.path.join(UPLOAD_FOLDER, '*.csv'))
        for file_path in uploaded_files:
            try:
                os.remove(file_path)
                print(f"Deleted upload: {file_path}")
                deleted_items.append(f"upload: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")

        # Delete output files in output/
        output_dir = './output'
        if os.path.exists(output_dir):
            try:
                output_files = glob.glob(os.path.join(output_dir, '*'))
                for file_path in output_files:
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"Deleted output file: {file_path}")
                            deleted_items.append(f"output: {os.path.basename(file_path)}")
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                            print(f"Deleted output dir: {file_path}")
                            deleted_items.append(f"output: {os.path.basename(file_path)}/")
                    except Exception as e:
                        print(f"Failed to delete {file_path}: {e}")
            except Exception as e:
                print(f"Error accessing output directory: {e}")

        # Delete flask_session files
        session_dir = './flask_session'
        if os.path.exists(session_dir):
            try:
                session_files = glob.glob(os.path.join(session_dir, '*'))
                for file_path in session_files:
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"Deleted session file: {file_path}")
                            deleted_items.append(f"session: {os.path.basename(file_path)}")
                    except Exception as e:
                        print(f"Failed to delete {file_path}: {e}")
            except Exception as e:
                print(f"Error accessing flask_session directory: {e}")

        return jsonify({
            'status': 'success',
            'message': 'All data cleared',
            'files_deleted': len(deleted_items),
            'deleted_items': deleted_items
        })

    except Exception as e:
        print(f"Error clearing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
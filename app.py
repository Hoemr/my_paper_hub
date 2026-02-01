# -*- coding: utf-8 -*-
import streamlit as st
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
import io
import re
import json
import os
import shutil
from pathlib import Path

# ================= CONFIGURATION & UTILITIES =================

st.set_page_config(page_title="PaperRef Hub", page_icon="📚", layout="wide")

# Initialize Session State
if 'db_entries' not in st.session_state:
    st.session_state.db_entries = [] # Store all bibliography entries
if 'selected_keys' not in st.session_state:
    st.session_state.selected_keys = set() # Store selected IDs

def safe_decode(bytes_data):
    """
    Try to decode bytes using different encodings to prevent errors.
    Priority: UTF-8 -> Latin-1 (Common in BibTeX) -> GBK -> Ignore Errors
    """
    encodings = ['utf-8', 'latin-1', 'gbk']
    for enc in encodings:
        try:
            return bytes_data.decode(enc)
        except UnicodeDecodeError:
            continue
    return bytes_data.decode('utf-8', errors='ignore')

def normalize_title(title):
    """Normalize title for duplicate detection (lowercase, remove non-alphanumeric)"""
    return re.sub(r'[^a-z0-9]', '', title.lower())

def normalize_id(entry_id):
    """Normalize entry ID for duplicate detection (lowercase, remove non-alphanumeric)"""
    return re.sub(r'[^a-z0-9]', '', str(entry_id).lower())

def merge_bib_data(existing_entries, new_bib_str):
    """
    Merge new BibTeX string into existing list.
    Logic: If title exists, keep the entry with MORE fields.
    """
    try:
        new_db = bibtexparser.loads(new_bib_str)
    except Exception as e:
        try:
            parser = BibTexParser()
            new_db = bibtexparser.loads(new_bib_str, parser=parser)
        except Exception as e2:
            st.error(f"Error parsing BibTeX: {e2}")
            return existing_entries, 0, 0
    
    # Create a map of existing entries: {normalized_title: entry_dict}
    entry_map = {normalize_title(e.get('title', '')): e for e in existing_entries}
    
    added_count = 0
    updated_count = 0
    
    for entry in new_db.entries:
        title = entry.get('title', '')
        if not title: continue 
        
        norm_title = normalize_title(title)
        
        if norm_title in entry_map:
            # Conflict: If new entry has more fields, update it.
            if len(entry) > len(entry_map[norm_title]):
                old_id = entry_map[norm_title].get('ID', entry.get('ID'))
                entry['ID'] = old_id # Preserve ID if possible
                entry_map[norm_title] = entry
                updated_count += 1
        else:
            entry_map[norm_title] = entry
            added_count += 1
            
    return list(entry_map.values()), added_count, updated_count

def remove_exact_duplicates(entries):
    """
    Remove exact duplicate entries based on normalized title and ID
    """
    seen_entries = set()
    unique_entries = []
    
    for entry in entries:
        norm_title = normalize_title(entry.get('title', ''))
        norm_id = normalize_id(entry.get('ID', ''))
        
        entry_key = (norm_title, norm_id)
        if entry_key not in seen_entries:
            seen_entries.add(entry_key)
            unique_entries.append(entry)
    
    return unique_entries

def find_similar_entries(entries, existing_entries):
    """
    Find entries with same ID or title (case-insensitive) for manual review
    Returns list of groups of similar entries, excluding exact matches
    """
    # Create normalized maps for existing entries
    existing_title_map = {normalize_title(e.get('title', '')): e for e in existing_entries}
    existing_id_map = {normalize_id(e.get('ID', '')): e for e in existing_entries}
    
    similar_groups = []
    processed = set()
    
    for i, entry1 in enumerate(entries):
        if i in processed:
            continue
            
        title1 = normalize_title(entry1.get('title', ''))
        id1 = normalize_id(entry1.get('ID', ''))
        
        similar_group = [entry1]
        processed.add(i)
        
        # Check against other new entries
        for j, entry2 in enumerate(entries[i+1:], i+1):
            if j in processed:
                continue
                
            title2 = normalize_title(entry2.get('title', ''))
            id2 = normalize_id(entry2.get('ID', ''))
            
            # Group if ID or title match (case-insensitive)
            if id1 == id2 or title1 == title2:
                similar_group.append(entry2)
                processed.add(j)
        
        # Check against existing library - if exact match found, skip this group
        if (title1 in existing_title_map and existing_title_map[title1]['ID'] == entry1.get('ID', '')) or \
           (id1 in existing_id_map and existing_id_map[id1]['title'] == entry1.get('title', '')):
            # Skip exact match with existing library
            continue
        
        if len(similar_group) > 1:
            similar_groups.append(similar_group)
    
    return similar_groups

def process_uploaded_files(uploaded_files):
    """
    Process uploaded files with conflict resolution
    """
    st.session_state.import_phase = 'processing'
    
    # Parse all files
    all_new_entries = []
    for u_file in uploaded_files:
        content = safe_decode(u_file.getvalue())
        
        try:
            # Try without custom parser first
            db = bibtexparser.loads(content)
            all_new_entries.extend(db.entries)
        except Exception as e:
            try:
                # Fallback with basic parser
                parser = BibTexParser()
                db = bibtexparser.loads(content, parser=parser)
                all_new_entries.extend(db.entries)
            except Exception as e2:
                st.error(f"Error parsing {u_file.name}: {e2}")
                continue
    
    if not all_new_entries:
        st.error("No valid entries found in uploaded files.")
        return
    
    # Remove exact duplicates from new entries first
    all_new_entries = remove_exact_duplicates(all_new_entries)
    
    # Check for similar entries
    similar_groups = find_similar_entries(all_new_entries, st.session_state.db_entries)
    
    if similar_groups:
        st.warning(f"⚠️ Found {len(similar_groups)} groups of similar entries. Please review:")
        
        # Store in session state for manual review
        st.session_state.similar_groups = similar_groups
        st.session_state.all_new_entries = all_new_entries
        st.session_state.import_phase = 'review'
    else:
        # Direct merge if no conflicts
        direct_merge_entries(all_new_entries)

def show_conflict_resolution():
    """
    Show interface for resolving conflicts
    """
    import time
    import random
    
    if 'similar_groups' not in st.session_state:
        return
        
    similar_groups = st.session_state.similar_groups
    
    # Initialize selection storage if not exists
    if 'conflict_selections' not in st.session_state:
        st.session_state.conflict_selections = {}
    
    # Check if we already processed this batch
    if 'conflicts_processed' in st.session_state and st.session_state.conflicts_processed:
        return

    st.subheader("🔍 Review Similar Entries")

    for i, group in enumerate(similar_groups):
        st.write(f"**Group {i+1}:** Similar titles found")
        
        # Use selectbox instead of radio to avoid key conflicts
        state_key = f"group_{i}_selection"
        
        # Initialize if not exists
        if state_key not in st.session_state.conflict_selections:
            st.session_state.conflict_selections[state_key] = 0
        
        options = list(range(len(group)))
        option_labels = [f"Option {x+1}: {group[x].get('title', 'No title')[:80]}..." for x in options]
        
        selected_label = st.selectbox(
            f"Choose which entry to keep for group {i+1}:",
            options=option_labels,
            index=st.session_state.conflict_selections[state_key],
            key=state_key
        )
        
        # Convert selected label back to index
        selected_option = option_labels.index(selected_label) if selected_label in option_labels else 0
        
        # Store the selection
        st.session_state.conflict_selections[state_key] = selected_option
        
        # Show detailed comparison
        cols = st.columns(len(group))
        
        for idx, (col, entry) in enumerate(zip(cols, group)):
            with col:
                is_selected = (idx == selected_option)
                if is_selected:
                    st.success(f"✅ Option {idx+1} (Selected)")
                else:
                    st.info(f"📄 Option {idx+1}")
                
                # Title
                title_text = entry.get('title', '').replace('{', '').replace('}', '')
                st.markdown(f"**Title:** {title_text[:80]}{'...' if len(title_text) > 80 else ''}")
                
                # Key info
                author_text = entry.get('author', '').replace('{', '').replace('}', '')
                if len(author_text) > 60:
                    author_text = author_text[:60] + '...'
                st.write(f"**Author:** {author_text}")
                st.write(f"**Year:** {entry.get('year', 'N/A')}")
                st.write(f"**Journal:** {entry.get('journal', entry.get('booktitle', 'N/A'))}")
                
                # All fields for detailed comparison
                with st.expander(f"🔍 All fields ({len(entry)} total)"):
                    for key, value in entry.items():
                        if key != 'ID':  # Skip ID in display
                            st.code(f"{key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                
                st.write(f"**ID:** `{entry.get('ID', 'N/A')}`")
        
        st.divider()
    
    # Continue Import Button
    if st.button("✅ Continue Import", key="continue_import_btn", type="primary"):
        resolved_entries = []
        
        # Collect selected entries from each group
        for i, group in enumerate(similar_groups):
            state_key = f"group_{i}_selection"
            selected_idx = st.session_state.conflict_selections.get(state_key, 0)
            selected_entry = group[selected_idx]
            resolved_entries.append(selected_entry)
        
        # Add non-conflicting entries
        conflict_ids = {entry.get('ID', '') for group in similar_groups for entry in group}
        non_conflicting = [e for e in st.session_state.all_new_entries 
                          if e.get('ID', '') not in conflict_ids]
        resolved_entries.extend(non_conflicting)
        
        direct_merge_entries(resolved_entries)
        st.session_state.import_phase = 'complete'
        st.session_state.conflicts_processed = True
    


def direct_merge_entries(entries_to_import):
    """
    Direct merge without conflicts
    """
    total_added = 0
    total_updated = 0
    
    # Generate BibTeX string for all entries
    temp_db = BibDatabase()
    temp_db.entries = entries_to_import
    writer = BibTexWriter()
    bib_str = bibtexparser.dumps(temp_db)
    
    merged_list, added, updated = merge_bib_data(st.session_state.db_entries, bib_str)
    st.session_state.db_entries = merged_list
    total_added += added
    total_updated += updated
    
    st.success(f"✅ Import complete! Added {total_added}, Updated {total_updated}.")
    
    # Clean up session state
    for key in ['similar_groups', 'all_new_entries', 'import_phase', 'conflict_selections', 'conflicts_processed']:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

def generate_bib_string(entries):
    """Convert dictionary list back to BibTeX string"""
    db = BibDatabase()
    db.entries = entries
    writer = BibTexWriter()
    return bibtexparser.dumps(db)

# ================= CACHE MANAGEMENT =================

CACHE_DIR = Path("cache")
WEBDAV_CACHE_FILE = CACHE_DIR / "webdav_config.json"
LIBRARY_CACHE_DIR = CACHE_DIR / "libraries"

def ensure_cache_dirs():
    """Create cache directories if they don't exist"""
    CACHE_DIR.mkdir(exist_ok=True)
    LIBRARY_CACHE_DIR.mkdir(exist_ok=True)

def save_webdav_config(hostname, login, password, filename):
    """Save WebDAV config to local cache"""
    ensure_cache_dirs()
    config = {
        "hostname": hostname,
        "login": login,
        "password": password,
        "filename": filename
    }
    with open(WEBDAV_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def load_webdav_config():
    """Load WebDAV config from local cache"""
    if WEBDAV_CACHE_FILE.exists():
        try:
            with open(WEBDAV_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_library_to_cache(entries, filename):
    """Save library entries to cache file"""
    ensure_cache_dirs()
    cache_file = LIBRARY_CACHE_DIR / filename
    bib_str = generate_bib_string(entries)
    with open(cache_file, 'w', encoding='utf-8') as f:
        f.write(bib_str)
    return cache_file

def load_library_from_cache(filename):
    """Load library entries from cache file"""
    cache_file = LIBRARY_CACHE_DIR / filename
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
                db = bibtexparser.loads(content)
                return db.entries
        except Exception as e:
            st.error(f"Error loading cache file: {e}")
    return None

def get_cached_libraries():
    """Get list of cached library files"""
    ensure_cache_dirs()
    return list(LIBRARY_CACHE_DIR.glob("*.bib"))

def share_library_file(filename):
    """Create a copy of library file for sharing"""
    cache_file = LIBRARY_CACHE_DIR / filename
    if cache_file.exists():
        # Create share directory if it doesn't exist
        share_dir = Path("share")
        share_dir.mkdir(exist_ok=True)
        
        # Create timestamped copy
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        share_file = share_dir / f"{filename.rsplit('.', 1)[0]}_share_{timestamp}.bib"
        
        shutil.copy2(cache_file, share_file)
        return share_file
    return None

# ================= WEBDAV SYNC MODULE =================
import requests
from requests.auth import HTTPBasicAuth
import warnings
warnings.filterwarnings('ignore')

def sync_from_cloud(hostname, login, password, filename="my_library.bib"):
    try:
        url = f"{hostname}{filename}" if not hostname.endswith('/') else f"{hostname}{filename}"
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        session = requests.Session()
        session.verify = False
        response = session.get(url, auth=HTTPBasicAuth(login, password), timeout=30)
        
        if response.status_code == 200:
            remote_str = safe_decode(response.content)
            
            try:
                db = bibtexparser.loads(remote_str)
            except Exception as e:
                parser = BibTexParser()
                db = bibtexparser.loads(remote_str, parser=parser)
            st.session_state.db_entries = db.entries
            return True, f"Success! Loaded {len(db.entries)} entries from cloud."
        elif response.status_code == 404:
            return False, "File not found on cloud. Ready to upload."
        else:
            return False, f"Download failed: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Sync Failed: {str(e)}"

def sync_to_cloud(hostname, login, password, filename="my_library.bib"):
    try:
        bib_str = generate_bib_string(st.session_state.db_entries)
        url = f"{hostname}{filename}" if not hostname.endswith('/') else f"{hostname}{filename}"
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        session = requests.Session()
        session.verify = False
        response = session.put(
            url, 
            data=bib_str.encode('utf-8'),
            auth=HTTPBasicAuth(login, password),
            headers={'Content-Type': 'application/x-bibtex'},
            timeout=30
        )
        
        if response.status_code in [200, 201, 204]:
            return True, "Success! Uploaded to cloud."
        else:
            return False, f"Upload failed: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Upload Failed: {str(e)}"

# ================= SIDEBAR: SETUP & IMPORT =================

with st.sidebar:
    st.header("☁️ WebDAV Setup")
    with st.expander("Cloud Settings", expanded=True):
        # Load cached config if available
        cached_config = load_webdav_config()
        
        wd_host = st.text_input("URL", 
                               value=cached_config.get('hostname', 'https://dav.jianguoyun.com/dav/') if cached_config else "https://dav.jianguoyun.com/dav/")
        wd_user = st.text_input("Username/Email", 
                               value=cached_config.get('login', '') if cached_config else '')
        wd_pass = st.text_input("App Password", 
                               value=cached_config.get('password', '') if cached_config else '', 
                               type="password")
        wd_file = st.text_input("Filename", 
                               value=cached_config.get('filename', 'my_library.bib') if cached_config else 'my_library.bib')
        
        # Save config when changed
        if st.button("💾 Save WebDAV Config"):
            save_webdav_config(wd_host, wd_user, wd_pass, wd_file)
            st.success("Config saved to cache!")
        
        col_sync1, col_sync2 = st.columns(2)
        if col_sync1.button("⬇️ Pull"):
            success, msg = sync_from_cloud(wd_host, wd_user, wd_pass, wd_file)
            if success: 
                st.success(msg)
                # Auto-save pulled library to cache
                save_library_to_cache(st.session_state.db_entries, wd_file)
            else: 
                st.warning(msg)
            
        if col_sync2.button("⬆️ Push"):
            if not st.session_state.db_entries:
                st.error("Library is empty.")
            else:
                success, msg = sync_to_cloud(wd_host, wd_user, wd_pass, wd_file)
                if success: 
                    st.success(msg)
                    # Auto-save pushed library to cache
                    save_library_to_cache(st.session_state.db_entries, wd_file)
                else: 
                    st.error(msg)

    st.divider()
    st.header("📚 Library Management")
    
    # Show cached libraries
    cached_libs = get_cached_libraries()
    if cached_libs:
        st.write("📁 **Cached Libraries:**")
        for lib_file in cached_libs:
            lib_name = lib_file.name
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"📄 {lib_name}")
            with col2:
                if st.button("📂", key=f"open_folder_{lib_name}", help="Open folder"):
                    try:
                        os.startfile(str(LIBRARY_CACHE_DIR))
                    except Exception as e:
                        st.error(f"Could not open folder: {e}")
            with col3:
                if st.button("🔄", key=f"load_lib_{lib_name}", help="Load library"):
                    entries = load_library_from_cache(lib_name)
                    if entries:
                        st.session_state.db_entries = entries
                        st.success(f"Loaded {len(entries)} entries from {lib_name}")
                        st.rerun()
    
    st.divider()
    st.header("📥 Import")
    
    # Import method selection
    import_method = st.radio("Choose import method:", ["📁 Local Files", "☁️ WebDAV"])
    
    if import_method == "📁 Local Files":
        st.write("Select BibTeX files to import:")
        uploaded_files = st.file_uploader("Upload .bib files", accept_multiple_files=True, type=['bib'])
        
        if uploaded_files:
            if st.button("📥 Import Files", type="primary"):
                process_uploaded_files(uploaded_files)
    
    elif import_method == "☁️ WebDAV":
        if not all([wd_host, wd_user, wd_pass]):
            st.warning("⚠️ Please configure WebDAV settings above first.")
        else:
            if st.button("📥 Import from WebDAV", type="primary"):
                success, msg = sync_from_cloud(wd_host, wd_user, wd_pass, wd_file)
                if success:
                    st.success(msg)
                    # Auto-save to cache
                    save_library_to_cache(st.session_state.db_entries, wd_file)
                    st.rerun()
                else:
                    st.error(msg)

# ================= MAIN UI =================

# Check for ongoing import process
if hasattr(st.session_state, 'import_phase') and st.session_state.import_phase == 'review':
    show_conflict_resolution()
    st.stop()

st.title("📚 Research Canvas (PaperRef Hub)")

# --- Library Actions ---
col_save, col_share, col_search, col_actions = st.columns([1, 1, 2, 1])

with col_save:
    if st.button("💾 Save Library"):
        filename = st.text_input("Library filename:", value="my_library.bib", key="save_filename")
        if filename:
            if not filename.endswith('.bib'):
                filename += '.bib'
            cache_file = save_library_to_cache(st.session_state.db_entries, filename)
            st.success(f"Library saved as {filename}")

with col_share:
    if st.button("📤 Share Library"):
        cached_libs = get_cached_libraries()
        if cached_libs:
            lib_to_share = st.selectbox("Select library to share:", 
                                      [lib.name for lib in cached_libs], 
                                      key="share_select")
            if st.button("📋 Create Share Copy", key="create_share"):
                share_file = share_library_file(lib_to_share)
                if share_file:
                    st.success(f"Share copy created: {share_file.name}")
                    st.info(f"File location: {share_file.absolute()}")
        else:
            st.warning("No cached libraries to share.")

# --- Top Bar ---
col_search, col_actions = st.columns([2, 1])

with col_search:
    search_query = st.text_input("🔍 Search (Title, Author, Year, Keyword)", placeholder="e.g., Attention, 2025...")

# Filter Logic
all_entries = st.session_state.db_entries
filtered_entries = []

if search_query:
    q = search_query.lower()
    for e in all_entries:
        content = " ".join([str(v) for v in e.values()]).lower()
        if q in content:
            filtered_entries.append(e)
else:
    filtered_entries = all_entries

# --- Batch Actions ---
with col_actions:
    st.write("") 
    st.write("") 
    selected_count = len(st.session_state.selected_keys)
    if st.button(f"📋 Batch Copy BibTeX ({selected_count})"):
        if selected_count == 0:
            st.warning("No papers selected.")
        else:
            selected_entries = [e for e in all_entries if e.get('ID') in st.session_state.selected_keys]
            batch_bib = generate_bib_string(selected_entries)
            st.info("Copy the code below:")
            st.code(batch_bib, language="latex")

# --- List View ---
st.markdown(f"**Showing {len(filtered_entries)} papers**")
st.divider()

for i, entry in enumerate(filtered_entries):
    entry_id = entry.get('ID', f"ref_{i}")
    
    col_check, col_info, col_copy = st.columns([0.05, 0.8, 0.15])
    
    # Checkbox
    is_selected = entry_id in st.session_state.selected_keys
    if col_check.checkbox("Select", key=f"chk_{entry_id}", value=is_selected, label_visibility="hidden"):
        st.session_state.selected_keys.add(entry_id)
    else:
        st.session_state.selected_keys.discard(entry_id)
        
    # Info
    with col_info:
        title = entry.get('title', 'Untitled').replace('{', '').replace('}', '')
        author = entry.get('author', 'Unknown Authors')
        year = entry.get('year', 'N/A')
        journal = entry.get('journal', entry.get('booktitle', 'N/A'))
        
        st.markdown(f"#### {title}")
        st.caption(f"👤 **{author}** | 📅 {year} | 📄 {journal}")
        
        with st.expander("✏️ Edit Details"):
            with st.form(key=f"form_{entry_id}"):
                new_title = st.text_input("Title", value=entry.get('title', ''))
                new_author = st.text_input("Author", value=entry.get('author', ''))
                new_id = st.text_input("Citation Key (ID)", value=entry.get('ID', ''))
                
                if st.form_submit_button("💾 Save"):
                    entry['title'] = new_title
                    entry['author'] = new_author
                    entry['ID'] = new_id
                    st.toast(f"Updated: {new_title}")
                    st.rerun()

    # Copy Button
    with col_copy:
        st.write("")
        if st.button("Copy Bib", key=f"btn_{entry_id}"):
            single_bib = generate_bib_string([entry])
            st.code(single_bib, language="latex")

    st.divider()
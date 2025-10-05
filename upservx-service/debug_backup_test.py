#!/usr/bin/env python3
"""
Debug-Test für das Backup-System
Testet die komplette Backup-Pipeline mit detailliertem Logging
"""

import os
import sys
import json
from datetime import datetime

# Add service directory to path
sys.path.append('/home/m/Dokumente/Repo/upservx-full/upservx-service')

print("=" * 80)
print("BACKUP SYSTEM DEBUG TEST")
print("=" * 80)

try:
    # Import modules with error handling
    print("1. Importing modules...")
    
    try:
        from backup import BackupManager
        print("   ✓ BackupManager imported successfully")
    except Exception as e:
        print(f"   ✗ Failed to import BackupManager: {e}")
        sys.exit(1)
    
    try:
        from backup_db import backup_db
        print("   ✓ backup_db imported successfully")
    except Exception as e:
        print(f"   ✗ Failed to import backup_db: {e}")
        sys.exit(1)
    
    # Test database connection
    print("\n2. Testing database connection...")
    try:
        servers = backup_db.get_backup_servers()
        print(f"   ✓ Database connection OK, found {len(servers)} servers")
        for server in servers:
            print(f"   - {server['name']} ({server['type']})")
    except Exception as e:
        print(f"   ✗ Database connection failed: {e}")
        sys.exit(1)
    
    # Create test data
    print("\n3. Preparing test data...")
    
    # Create test source directory
    test_source_dir = '/tmp/backup_test_source'
    os.makedirs(test_source_dir, exist_ok=True)
    
    # Create test files
    test_files = [
        'test_file1.txt',
        'test_file2.txt', 
        'config.json'
    ]
    
    for filename in test_files:
        filepath = os.path.join(test_source_dir, filename)
        with open(filepath, 'w') as f:
            f.write(f"Test content for {filename}\nCreated at: {datetime.now()}\n")
            f.write("This is test data for backup testing.\n" * 10)
    
    print(f"   ✓ Created test source directory: {test_source_dir}")
    print(f"   ✓ Created {len(test_files)} test files")
    
    # Create or get test server
    print("\n4. Setting up backup server...")
    
    test_server_data = {
        'name': 'Debug Test Local Server',
        'type': 'local',
        'local_path': '/tmp/debug_backups'
    }
    
    # Check if server exists
    existing_server = None
    for server in backup_db.get_backup_servers():
        if server['name'] == test_server_data['name']:
            existing_server = server
            break
    
    if existing_server:
        test_server = existing_server
        print(f"   ✓ Using existing server: {test_server['name']}")
    else:
        server_id = backup_db.create_backup_server(test_server_data)
        test_server = backup_db.get_backup_server(server_id)
        print(f"   ✓ Created new server: {test_server['name']}")
    
    # Create test job
    print("\n5. Setting up backup job...")
    
    test_job_data = {
        'name': 'Debug Test Job',
        'backup_type': 'system',
        'targets': [test_source_dir, '/etc/hostname'],  # Include system file for testing
        'schedule': '0 2 * * *',
        'server_id': test_server['id'],
        'retention_days': 7,
        'compression': True
    }
    
    # Check if job exists
    existing_job = None
    for job in backup_db.get_backup_jobs():
        if job['name'] == test_job_data['name']:
            existing_job = job
            break
    
    if existing_job:
        test_job = existing_job
        print(f"   ✓ Using existing job: {test_job['name']}")
    else:
        job_id = backup_db.create_backup_job(test_job_data)
        test_job = backup_db.get_backup_job(job_id)
        print(f"   ✓ Created new job: {test_job['name']}")
    
    print(f"   Job targets: {test_job['targets']}")
    
    # Initialize backup manager
    print("\n6. Initializing BackupManager...")
    backup_manager = BackupManager()
    print("   ✓ BackupManager initialized")
    
    # Execute backup
    print("\n7. EXECUTING BACKUP...")
    print("=" * 60)
    
    result = backup_manager.execute_backup(test_job, test_server)
    
    print("=" * 60)
    print("BACKUP EXECUTION COMPLETED")
    print("=" * 60)
    
    # Display results
    print("\n8. Backup Results:")
    print(f"   Success: {result.get('success', False)}")
    
    if result.get('success'):
        print(f"   Backup Path: {result.get('backup_path')}")
        print(f"   Archive Size: {result.get('size', 0)} bytes")
        print(f"   File Count: {result.get('file_count', 0)}")
        print(f"   Compression Ratio: {result.get('compression_ratio', 0):.1f}%")
        print(f"   Duration: {result.get('duration', 0):.2f} seconds")
        
        # Verify backup file exists
        backup_path = result.get('backup_path')
        if backup_path and os.path.exists(backup_path):
            actual_size = os.path.getsize(backup_path)
            print(f"   ✓ Backup file verified: {actual_size} bytes")
            
            # List backup directory contents
            backup_dir = os.path.dirname(backup_path)
            if os.path.exists(backup_dir):
                files = os.listdir(backup_dir)
                print(f"   Backup directory contents ({len(files)} files):")
                for f in files:
                    f_path = os.path.join(backup_dir, f)
                    f_size = os.path.getsize(f_path)
                    print(f"     - {f} ({f_size} bytes)")
        else:
            print(f"   ✗ Backup file not found: {backup_path}")
    else:
        print(f"   Error: {result.get('error', 'Unknown error')}")
    
    print("\n9. Cleanup...")
    print("   Test completed - check /tmp/backup_debug.log for detailed logs")
    
except Exception as e:
    print(f"FATAL ERROR: {e}")
    import traceback
    print("FULL TRACEBACK:")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("DEBUG TEST COMPLETED")
print("=" * 80)
#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import psycopg2
import json
from datetime import datetime

def get_db_connection(module):
    """Get database connection with schema"""
    conn = psycopg2.connect(
        host=module.params['db_host'],
        database=module.params['db_name'],
        user=module.params['db_user'],
        password=module.params['db_password']
    )
    cursor = conn.cursor()
    # Set schema search path
    cursor.execute("SET search_path TO patch_tracking, public")
    return conn, cursor

def store_profiles(module, cursor):
    """Store discovered patch profiles"""
    cursor.execute('''
        INSERT INTO patch_profiles (patch_file, profiles, default_profile)
        VALUES (%s, %s, %s)
        ON CONFLICT (patch_file)
        DO UPDATE SET 
            profiles = EXCLUDED.profiles,
            default_profile = EXCLUDED.default_profile,
            discovered_at = CURRENT_TIMESTAMP
    ''', (
        module.params.get('patch_file'),
        json.dumps(module.params.get('profiles')),
        module.params.get('default_profile')
    ))
    return True, {"message": "Profiles stored"}

def store_precheck(module, cursor):
    """Store precheck results"""
    cursor.execute('''
        INSERT INTO host_precheck 
        (host_id, ssh_status, current_build, version_details, 
         selected_datastore, available_space_gb, precheck_timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (host_id)
        DO UPDATE SET 
            ssh_status = EXCLUDED.ssh_status,
            current_build = EXCLUDED.current_build,
            version_details = EXCLUDED.version_details,
            selected_datastore = EXCLUDED.selected_datastore,
            available_space_gb = EXCLUDED.available_space_gb,
            precheck_timestamp = EXCLUDED.precheck_timestamp,
            last_updated = CURRENT_TIMESTAMP
    ''', (
        module.params.get('host'),
        module.params.get('ssh_status'),
        module.params.get('current_build'),
        module.params.get('version_details'),
        module.params.get('selected_datastore'),
        module.params.get('available_space_gb'),
        module.params.get('timestamp')
    ))
    return True, {"message": "Precheck stored"}

def get_eligible_hosts(module, cursor):
    """Get hosts that passed precheck"""
    cursor.execute('''
        SELECT host_id, current_build, version_details, selected_datastore
        FROM host_precheck
        WHERE ssh_status = 'pass'
        AND selected_datastore != 'none'
        AND available_space_gb > 3
    ''')
    
    hosts = []
    for row in cursor.fetchall():
        hosts.append({
            'hostname': row[0],
            'current_build': row[1],
            'version_details': row[2],
            'selected_datastore': row[3]
        })
    
    return True, {"hosts": hosts}

def main():
    module = AnsibleModule(
        argument_spec=dict(
            action=dict(required=True, type='str'),
            db_host=dict(required=True, type='str'),
            db_name=dict(required=True, type='str'),
            db_user=dict(required=True, type='str'),
            db_password=dict(required=True, type='str', no_log=True),
            patch_file=dict(type='str'),
            profiles=dict(type='list'),
            default_profile=dict(type='str'),
            host=dict(type='str'),
            ssh_status=dict(type='str'),
            current_build=dict(type='str'),
            version_details=dict(type='str'),
            selected_datastore=dict(type='str'),
            available_space_gb=dict(type='float'),
            timestamp=dict(type='str'),
            eligibility_data=dict(type='dict'),
            selected_patch=dict(type='str'),
            selected_profile=dict(type='str')
        )
    )
    
    try:
        conn, cursor = get_db_connection(module)
        
        action_map = {
            'store_profiles': store_profiles,
            'store_precheck': store_precheck,
            'get_eligible_hosts': get_eligible_hosts
        }
        
        if module.params['action'] in action_map:
            success, result = action_map[module.params['action']](module, cursor)
            conn.commit()
            
            if success:
                module.exit_json(changed=True, **result)
            else:
                module.fail_json(msg=result.get('message', 'Operation failed'))
        else:
            module.fail_json(msg=f"Unknown action: {module.params['action']}")
            
    except Exception as e:
        module.fail_json(msg=f"Database operation failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()

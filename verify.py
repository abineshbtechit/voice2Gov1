import os

docs_dir = r'C:\Personal Projects\Voice2Gov\docs'

# Check PyMongo AsyncMongoClient in key files
files_to_check = [
    'architecture.md',
    'database-indexes.md', 
    'testing-strategy.md',
    'file-storage-architecture.md',
    'phase-0-decisions.md',
    'traceability-matrix.md',
]

print("=== PyMongo AsyncMongoClient check ===")
for f in files_to_check:
    path = os.path.join(docs_dir, f)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            found = 'PyMongo AsyncMongoClient' in content or 'pymongo.asynchronous.AsyncMongoClient' in content
            print('  {}: {}'.format(f, 'PASS' if found else 'FAIL'))

# Check visibility used, no stale is_public for complaints
files_vis = [
    'api-contract.md',
    'authentication-rbac.md',
    'complaint-state-machine.md',
    'notification-architecture.md',
    'priority-engine.md',
    'testing-strategy.md',
    'database-schema.md',
    'database-indexes.md',
    'traceability-matrix.md',
]

print("\n=== visibility check ===")
for f in files_vis:
    path = os.path.join(docs_dir, f)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fp:
            content = fp.read()
        has_vis = 'visibility' in content
        lines = content.split('\n')
        bad = False
        for line in lines:
            if 'is_public' in line and 'complaint' in line.lower():
                if 'replaces is_public' not in line and 'distinct from complaint' not in line and 'admin only' not in line:
                    bad = True
                    break
        print('  {}: {} - visibility={}, stale_is_public={}'.format(f, 'PASS' if has_vis and not bad else 'FAIL', has_vis, bad))

print("\n=== All checks complete ===")
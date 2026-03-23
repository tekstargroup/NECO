# Running Alembic Migration - Step by Step

## The Problem

You're getting errors because:
1. **Wrong directory**: You're in `~` (home directory) but need to be in the `backend` directory
2. **Virtual environment not activated**: `alembic` command is only available when the venv is activated

## Solution: Run These Commands

```bash
# 1. Navigate to the backend directory (use full path with spaces)
cd "/Users/stevenbigio/Cursor Projects/NECO/backend"

# 2. Activate the virtual environment
source ../venv_neco/bin/activate

# 3. Verify you're in the right place
pwd
# Should show: /Users/stevenbigio/Cursor Projects/NECO/backend

# 4. Verify alembic.ini exists
ls -la alembic.ini

# 5. Now run the migration
alembic upgrade head
```

## OR Use the Quick Script

I've created a script that does all of this automatically:

```bash
cd "/Users/stevenbigio/Cursor Projects/NECO/backend"
./QUICK_START_MIGRATION.sh
```

## Expected Output

After running `alembic upgrade head`, you should see:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001, add_classification_audit_table
```

## Verify Migration Worked

After the migration completes, verify the table was created:

```bash
# Connect to database
psql -h localhost -U neco -d neco

# Check if table exists
\dt classification_audit

# Or run a query
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_name = 'classification_audit';
-- Should return: 1
```

## Troubleshooting

### Error: "command not found: alembic"
- **Cause**: Virtual environment not activated
- **Fix**: Run `source ../venv_neco/bin/activate` first

### Error: "No config file 'alembic.ini' found"
- **Cause**: Not in the `backend` directory
- **Fix**: `cd "/Users/stevenbigio/Cursor Projects/NECO/backend"` first

### Error: "cd: no such file or directory: backend"
- **Cause**: You're in the wrong starting directory
- **Fix**: Use the full path: `cd "/Users/stevenbigio/Cursor Projects/NECO/backend"`

### Error: "sqlalchemy.url not set"
- **Cause**: Database URL not in `.env` file
- **Fix**: Ensure `.env` file exists in the project root with `DATABASE_URL=postgresql+asyncpg://neco:neco_dev_password@localhost:5432/neco`

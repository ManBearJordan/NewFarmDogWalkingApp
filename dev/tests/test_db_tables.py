import sqlite3

conn = sqlite3.connect('app.db')
c = conn.cursor()

# Check if sub_schedules table exists
try:
    c.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="sub_schedules"')
    result = c.fetchone()
    if result:
        print('sub_schedules table exists')
        c.execute('PRAGMA table_info(sub_schedules)')
        columns = c.fetchall()
        print('sub_schedules table structure:')
        for col in columns:
            print(f'  {col[1]} {col[2]} (nullable: {not col[3]})')
    else:
        print('sub_schedules table does not exist yet')
except Exception as e:
    print(f'Error checking sub_schedules: {e}')

print()

# Check existing sub_occurrences table
try:
    c.execute('PRAGMA table_info(sub_occurrences)')
    columns = c.fetchall()
    print('Existing sub_occurrences table structure:')
    for col in columns:
        print(f'  {col[1]} {col[2]} (nullable: {not col[3]})')
except Exception as e:
    print(f'Error checking sub_occurrences: {e}')

conn.close()

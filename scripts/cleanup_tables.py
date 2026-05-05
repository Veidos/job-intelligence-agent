import sqlite3
conn = sqlite3.connect('data/jobs.db')
for tabla in ['skills', 'offer_skills', 'candidate_skills',
              'evaluations', 'evaluation_patterns', 'migration_log']:
    conn.execute(f'DROP TABLE IF EXISTS {tabla}')
conn.commit()
conn.close()
print('OK')

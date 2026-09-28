CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
       full_name VARCHAR(255) NOT NULL DEFAULT '',
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'USER',
    email_verified BOOLEAN NOT NULL DEFAULT TRUE
);

-- Demo account: demo@example.com / password          
INSERT INTO users (full_name, email, password, role)
VALUES (
    'Demo User',
    'demo@example.com',
    '$2b$10$FU4TOKJnRaBG2pTNPAYyYOfdQfhDymwWw78IP8lCY20oivb0P0suO',
    'USER',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    password = EXCLUDED.password,
    role = EXCLUDED.role,
    email_verified = EXCLUDED.email_verified;

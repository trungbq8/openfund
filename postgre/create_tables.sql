CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE raiser (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    x_link VARCHAR(100),
    website_link VARCHAR(100),
    email VARCHAR(255) UNIQUE NOT NULL,
    email_confirmed BOOLEAN DEFAULT FALSE,
    hashed_password TEXT NOT NULL,
    salt TEXT NOT NULL,
    bio TEXT,
    wallet_address VARCHAR(255) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    logo_url TEXT
);

CREATE TABLE investor (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE,
    logo_url TEXT
);

CREATE TABLE transaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id INT NOT NULL,
    investor_address VARCHAR(255) NOT NULL,
    amount INT,
    token_received INT,
    transaction_time TIMESTAMP NOT NULL,
    transaction_hash VARCHAR(255) NOT NULL,
    type VARCHAR(20) CHECK (type IN ('investment', 'vote', 'get_refund')) DEFAULT 'investment',
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_address) REFERENCES investor(wallet_address) ON DELETE CASCADE,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE project (
    id SERIAL PRIMARY KEY,
    raiser_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    token_name VARCHAR(50) NOT NULL,
    token_symbol VARCHAR(10) NOT NULL,
    logo_url TEXT,
    investment_end_time bigint NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    listing_status VARCHAR(20) CHECK (listing_status IN ('pending', 'accepted')) DEFAULT 'pending',
    hidden BOOLEAN DEFAULT FALSE,
    funding_status VARCHAR(20) CHECK (funding_status IN ('not listed', 'created', 'raising', 'voting', 'failed', 'completed')) DEFAULT 'not listed',
    total_token_supply bigint NOT NULL,
    token_to_sell bigint NOT NULL,
    token_price DECIMAL(18, 8) NOT NULL,
    token_address VARCHAR(255) NOT NULL,
    funding_address VARCHAR(255) NOT NULL,
    fund_raised bigint NOT NULL,
    token_sold bigint NOT NULL,
    decimal INT NOT NULL,
    fund_claimed BOOLEAN DEFAULT FALSE,
    platform_fee_claimed BOOLEAN DEFAULT FALSE,
    vote_for_refund bigint NOT NULL,
    x_link VARCHAR(100),
    website_link VARCHAR(100),
    telegram_link VARCHAR(100),
    whitepaper_link VARCHAR(100),
    description TEXT NOT NULL,
    editable BOOLEAN DEFAULT TRUE,
    platform_comment TEXT NOT NULL,
    FOREIGN KEY (raiser_id) REFERENCES raiser(id) ON DELETE CASCADE
);

CREATE TABLE post (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    thumbnail_url TEXT NOT NULL,
    status VARCHAR(10) CHECK (status IN ('draft', 'posted')) DEFAULT 'draft'
);

CREATE TABLE project_like (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id INT NOT NULL,
    investor_id UUID NOT NULL,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investor(id) ON DELETE CASCADE
);

CREATE TABLE project_comment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id INT NOT NULL,
    comment_text TEXT NOT NULL,
    investor_id UUID NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investor(id) ON DELETE CASCADE
);

CREATE TABLE admin (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    salt TEXT NOT NULL,
    last_login TIMESTAMP
);
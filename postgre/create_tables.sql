CREATE TABLE raiser (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    bio TEXT,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    salt TEXT NOT NULL,
    country VARCHAR(100),
    wallet_address VARCHAR(255) UNIQUE NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE investor (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    logo_url TEXT
);

CREATE TABLE project (
    id SERIAL PRIMARY KEY,
    raiser_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    logo_url TEXT,
    investment_end_time TIMESTAMP NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    listing_status VARCHAR(20) CHECK (listing_status IN ('pending', 'accepted')) DEFAULT 'pending',
    hidden BOOLEAN DEFAULT false;
    funding_status VARCHAR(20) CHECK (funding_status IN ('not listed', 'created', 'raising', 'voting', 'failed', 'completed')) DEFAULT 'not listed',
    total_token_supply INT NOT NULL,
    token_to_sell INT NOT NULL,
    token_price DECIMAL(18, 8) NOT NULL,
    end_time TIMESTAMP NOT NULL,
    FOREIGN KEY (raiser_id) REFERENCES raiser(id) ON DELETE CASCADE,
);

CREATE TABLE post (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(10) CHECK (status IN ('draft', 'posted')) DEFAULT 'draft',
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

CREATE TABLE blog_post (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(10) CHECK (status IN ('draft', 'posted')) DEFAULT 'draft',
);

CREATE TABLE post_photo (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL,
    photo_url TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

CREATE TABLE post_like (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    investor_id INT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investor(id) ON DELETE CASCADE
);

CREATE TABLE post_comment (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    comment_text TEXT NOT NULL,
    investor_id INT NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investor(id) ON DELETE CASCADE
);
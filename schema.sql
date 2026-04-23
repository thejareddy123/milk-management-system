-- Milk Management System Database Schema
CREATE DATABASE IF NOT EXISTS milk_management;
USE milk_management;

-- Admins
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    aadhaar VARCHAR(12) NOT NULL,
    business_name VARCHAR(150) NOT NULL,
    location VARCHAR(200) NOT NULL,
    password VARCHAR(255) NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    is_active BOOLEAN DEFAULT TRUE,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Providers
CREATE TABLE IF NOT EXISTS providers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    aadhaar VARCHAR(12) NOT NULL,
    supplier_id INT NOT NULL,
    password VARCHAR(255) NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    is_active BOOLEAN DEFAULT TRUE,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Milk Rates (defined by admin)
CREATE TABLE IF NOT EXISTS milk_rates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fat_min DECIMAL(4,2) NOT NULL,
    fat_max DECIMAL(4,2) NOT NULL,
    snf_min DECIMAL(4,2) NOT NULL,
    snf_max DECIMAL(4,2) NOT NULL,
    price_per_liter DECIMAL(8,2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Milk Entries
CREATE TABLE IF NOT EXISTS milk_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider_id INT NOT NULL,
    supplier_id INT NOT NULL,
    entry_date DATE NOT NULL,
    session ENUM('morning', 'evening') NOT NULL,
    quantity DECIMAL(8,2) NOT NULL,
    fat DECIMAL(4,2) NOT NULL,
    snf DECIMAL(4,2) NOT NULL,
    rate_id INT,
    price_per_liter DECIMAL(8,2) NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_entry (provider_id, entry_date, session),
    FOREIGN KEY (provider_id) REFERENCES providers(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (rate_id) REFERENCES milk_rates(id)
);

-- Feedback
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    user_type ENUM('supplier', 'provider') NOT NULL,
    subject VARCHAR(200),
    message TEXT NOT NULL,
    status ENUM('pending', 'resolved') DEFAULT 'pending',
    admin_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- OTP Store (temporary)
CREATE TABLE IF NOT EXISTS otp_store (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    otp_hash VARCHAR(64) NOT NULL,
    purpose ENUM('register', 'forgot_password') NOT NULL,
    expires_at DATETIME NOT NULL,
    last_sent_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email_purpose (email, purpose)
);

-- Rejected registrations log (so rejected users can re-register)
CREATE TABLE IF NOT EXISTS registration_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    role ENUM('supplier', 'provider') NOT NULL,
    reason TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

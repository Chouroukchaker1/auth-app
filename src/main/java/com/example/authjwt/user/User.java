package com.example.authjwt.user;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(name = "users", uniqueConstraints = @UniqueConstraint(columnNames = "email"))
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String fullName;
    private String email;
    private String password;
    private String role;
    private boolean emailVerified = true;
    private String emailVerificationToken;
    private java.time.Instant emailVerificationTokenExpiresAt;
    private String passwordResetCode;
    private java.time.Instant passwordResetCodeExpiresAt;

    @Column(columnDefinition = "bytea")
    private byte[] photo;
    private String photoContentType;

    protected User() {
    }

    public User(String fullName, String email, String password, String role) {
        this.fullName = fullName;
        this.email = email;
        this.password = password;
        this.role = role;
    }

    public void markEmailAsUnverified(String token, java.time.Instant expiresAt) {
        this.emailVerified = false;
        this.emailVerificationToken = token;
        this.emailVerificationTokenExpiresAt = expiresAt;
    }

    public void markEmailAsVerified() {
        this.emailVerified = true;
        this.emailVerificationToken = null;
        this.emailVerificationTokenExpiresAt = null;
    }

    public Long getId() { return id; }
    public String getFullName() { return fullName; }
    public String getEmail() { return email; }
    public String getPassword() { return password; }
    public String getRole() { return role; }
    public boolean isEmailVerified() { return emailVerified; }
    public String getEmailVerificationToken() { return emailVerificationToken; }
    public java.time.Instant getEmailVerificationTokenExpiresAt() { return emailVerificationTokenExpiresAt; }

    public void setFullName(String fullName) { this.fullName = fullName; }
    public void setEmail(String email) { this.email = email; }
    public void setRole(String role) { this.role = role; }
    public void setPassword(String password) { this.password = password; }
    public void setPasswordResetCode(String passwordResetCode) { this.passwordResetCode = passwordResetCode; }
    public void setPasswordResetCodeExpiresAt(java.time.Instant passwordResetCodeExpiresAt) {
        this.passwordResetCodeExpiresAt = passwordResetCodeExpiresAt;
    }
    public String getPasswordResetCode() { return passwordResetCode; }
    public java.time.Instant getPasswordResetCodeExpiresAt() { return passwordResetCodeExpiresAt; }

    public byte[] getPhoto() { return photo; }
    public void setPhoto(byte[] photo) { this.photo = photo; }
    public String getPhotoContentType() { return photoContentType; }
    public void setPhotoContentType(String photoContentType) { this.photoContentType = photoContentType; }
}

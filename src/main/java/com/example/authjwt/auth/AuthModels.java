package com.example.authjwt.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

record AuthResponse(String token) {
}

record LoginRequest(@Email @NotBlank String email, @NotBlank String password) {
}

record RegisterRequest(
        @NotBlank @Size(max = 255) String fullName,
        @Email @NotBlank String email,
        @NotBlank @Size(min = 8, max = 100) String password) {
}

record ForgotPasswordRequest(@Email @NotBlank String email) {
}

record ResetPasswordRequest(
    @Email @NotBlank String email,
    @NotBlank @Size(min = 6, max = 6) String code,
    @NotBlank @Size(min = 8, max = 100) String newPassword) {
}

record MessageResponse(String message) {
}

@Service
class PasswordService {
    private final PasswordEncoder encoder;

    PasswordService(PasswordEncoder encoder) {
        this.encoder = encoder;
    }

    String encode(String password) {
        return encoder.encode(password);
    }
} 
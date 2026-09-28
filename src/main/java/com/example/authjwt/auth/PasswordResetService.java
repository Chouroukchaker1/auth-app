package com.example.authjwt.auth;
import com.example.authjwt.user.User;
import com.example.authjwt.user.UserRepository;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
class PasswordResetService {
    private static final Duration CODE_VALIDITY = Duration.ofMinutes(10);

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;            
    private final JavaMailSender mailSender;
    private final String mailFrom;
    private final SecureRandom secureRandom = new SecureRandom();

    PasswordResetService(UserRepository userRepository, PasswordEncoder passwordEncoder,
                         JavaMailSender mailSender, @Value("${app.mail.from}") String mailFrom) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.mailSender = mailSender;
        this.mailFrom = mailFrom;
    }

    @Transactional
    void sendResetCode(String email) {
        userRepository.findByEmail(normalize(email)).ifPresent(user -> {
            String code = String.format("%06d", secureRandom.nextInt(1_000_000));
            user.setPasswordResetCode(passwordEncoder.encode(code));
            user.setPasswordResetCodeExpiresAt(Instant.now().plus(CODE_VALIDITY));
            userRepository.save(user);
            sendEmail(user, code);
        });
    }

    @Transactional
    void resetPassword(ResetPasswordRequest request) {
        User user = userRepository.findByEmail(normalize(request.email()))
                .orElseThrow(this::invalidCodeException);
        if (user.getPasswordResetCode() == null || user.getPasswordResetCodeExpiresAt() == null
                || user.getPasswordResetCodeExpiresAt().isBefore(Instant.now())
                || !passwordEncoder.matches(request.code(), user.getPasswordResetCode())) {
            throw invalidCodeException();
        }

        user.setPassword(passwordEncoder.encode(request.newPassword()));
        user.setPasswordResetCode(null);
        user.setPasswordResetCodeExpiresAt(null);
        userRepository.save(user);
    }

    private void sendEmail(User user, String code) {
        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(mailFrom);
        message.setTo(user.getEmail());
        message.setSubject("Code de récupération de votre mot de passe");
        message.setText("Bonjour " + user.getFullName() + ",\n\n"
                + "Votre code de récupération est : " + code + "\n"
                + "Ce code est valable pendant 10 minutes.\n\n"
                + "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.");
        try {
            mailSender.send(message);
        } catch (MailException exception) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Le service d'envoi d'e-mails n'est pas configuré ou est indisponible",
                    exception);
        }
    }

    private String normalize(String email) {
        return email.trim().toLowerCase(java.util.Locale.ROOT);
    }

    private ResponseStatusException invalidCodeException() {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, "Code invalide ou expiré");
    }
}
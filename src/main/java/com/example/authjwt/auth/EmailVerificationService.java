package com.example.authjwt.auth;

import com.example.authjwt.user.User;
import com.example.authjwt.user.UserRepository;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
class EmailVerificationService {
    private static final Duration TOKEN_VALIDITY = Duration.ofHours(24);

    private final UserRepository userRepository;
    private final JavaMailSender mailSender;
    private final String mailFrom;
    private final String frontendUrl;
    private final SecureRandom secureRandom = new SecureRandom();

    EmailVerificationService(UserRepository userRepository, JavaMailSender mailSender,
                             @Value("${app.mail.from}") String mailFrom,
                             @Value("${app.frontend-url}") String frontendUrl) {
        this.userRepository = userRepository;
        this.mailSender = mailSender;
        this.mailFrom = mailFrom;
        this.frontendUrl = frontendUrl;
    }

    @Transactional
    void sendVerificationEmail(User user) {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        user.markEmailAsUnverified(token, Instant.now().plus(TOKEN_VALIDITY));
        userRepository.save(user);

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(mailFrom);
        message.setTo(user.getEmail());
        message.setSubject("Validez votre adresse email");
        message.setText("Bonjour " + user.getFullName() + ",\n\n"
                + "Cliquez sur ce lien pour valider votre adresse email :\n"
                + frontendUrl + "/verify-email?token=" + token + "\n\n"
                + "Ce lien est valable pendant 24 heures.");
        try {
            mailSender.send(message);
        } catch (MailException exception) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Le service d'envoi d'e-mails n'est pas configuré ou est indisponible", exception);
        }
    }

    @Transactional
    void verify(String token) {
        User user = userRepository.findByEmailVerificationToken(token)
                .orElseThrow(this::invalidToken);
        if (user.getEmailVerificationTokenExpiresAt() == null
                || user.getEmailVerificationTokenExpiresAt().isBefore(Instant.now())) {
            throw invalidToken();
        }
        user.markEmailAsVerified();
        userRepository.save(user);
    }

    private ResponseStatusException invalidToken() {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, "Lien de validation invalide ou expiré");
    }
}
package com.example.authjwt;

import com.example.authjwt.user.User;
import com.example.authjwt.user.UserRepository;
import java.util.Locale;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.security.crypto.password.PasswordEncoder;

@SpringBootApplication
public class AuthJwtApplication {
    public static void main(String[] args) {
        SpringApplication.run(AuthJwtApplication.class, args);
    }

    @Bean
    CommandLineRunner promoteConfiguredAdmin(UserRepository userRepository,
                                             PasswordEncoder passwordEncoder,
                                             @Value("${app.admin.email:}") String adminEmail,
                                             @Value("${app.admin.password:}") String adminPassword) {
        return args -> {
            if (adminEmail == null || adminEmail.isBlank()) {
                return;
            }
            String normalizedEmail = adminEmail.trim().toLowerCase(Locale.ROOT);
            User user = userRepository.findByEmail(normalizedEmail).orElseGet(() ->
                    new User("Administrateur", normalizedEmail, "", "ADMIN"));
            user.setRole("ADMIN");
                if (adminPassword != null && !adminPassword.isBlank()
                    && (user.getPassword() == null || user.getPassword().isBlank()
                    || !passwordEncoder.matches(adminPassword, user.getPassword()))) {
                user.setPassword(passwordEncoder.encode(adminPassword));
            }
            userRepository.save(user);
        };
    }
}
 
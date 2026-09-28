package com.example.authjwt.auth;

import com.example.authjwt.security.JwtAuthenticationFilter.JwtService;
import com.example.authjwt.user.User;
import com.example.authjwt.user.UserRepository;
import jakarta.validation.Valid;
import java.io.IOException;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final UserRepository userRepository;
    private final PasswordService passwordService;
    private final AuthenticationManager authenticationManager;   
    private final UserDetailsService userDetailsService;
    private final JwtService jwtService;
    private final PasswordResetService passwordResetService;
    private final EmailVerificationService emailVerificationService;

    public AuthController(UserRepository userRepository, PasswordService passwordService,
                          AuthenticationManager authenticationManager, UserDetailsService userDetailsService,
                          JwtService jwtService, PasswordResetService passwordResetService,
                          EmailVerificationService emailVerificationService) {
        this.userRepository = userRepository;
        this.passwordService = passwordService;
        this.authenticationManager = authenticationManager;
        this.userDetailsService = userDetailsService;
        this.jwtService = jwtService;
        this.passwordResetService = passwordResetService;
        this.emailVerificationService = emailVerificationService;
    }

    @PostMapping(value = "/register", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public MessageResponse register(@Valid @RequestPart("data") RegisterRequest request,
                                     @RequestPart(value = "photo", required = false) MultipartFile photo)
            throws IOException {
        String normalizedEmail = request.email().trim().toLowerCase(java.util.Locale.ROOT);
        if (userRepository.existsByEmail(normalizedEmail)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Cet email est déjà utilisé");
        }
        User user = new User(request.fullName(), normalizedEmail,
            passwordService.encode(request.password()), "USER");
        user.markEmailAsUnverified(null, null);
        if (photo != null && !photo.isEmpty()) {
            user.setPhoto(photo.getBytes());
            user.setPhotoContentType(photo.getContentType());
        }
        user = userRepository.save(user);
        emailVerificationService.sendVerificationEmail(user);
        return new MessageResponse("Un email de validation a été envoyé. Vérifiez votre boîte mail avant de vous connecter.");
    }

    @PostMapping("/login")
    public AuthResponse login(@Valid @RequestBody LoginRequest request) {
        String normalizedEmail = request.email().trim().toLowerCase(java.util.Locale.ROOT);
        User user = userRepository.findByEmail(normalizedEmail)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Identifiants invalides"));
        if (!user.isEmailVerified()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN,
                "Veuillez valider votre adresse email avant de vous connecter");
        }
        authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(normalizedEmail, request.password()));
        UserDetails details = userDetailsService.loadUserByUsername(normalizedEmail);
        return new AuthResponse(jwtService.generateToken(details));
    }

    @PostMapping("/forgot-password")
    public MessageResponse forgotPassword(@Valid @RequestBody ForgotPasswordRequest request) {
        passwordResetService.sendResetCode(request.email());
        return new MessageResponse("Si cet email existe, un code de récupération a été envoyé.");
    }

    @PostMapping("/reset-password")
    public MessageResponse resetPassword(@Valid @RequestBody ResetPasswordRequest request) {
        passwordResetService.resetPassword(request);
        return new MessageResponse("Votre mot de passe a été modifié.");
    }

    @GetMapping("/verify-email")
    public MessageResponse verifyEmail(@RequestParam String token) {
        emailVerificationService.verify(token);
        return new MessageResponse("Votre adresse email est validée. Vous pouvez maintenant vous connecter.");
    }
}






 
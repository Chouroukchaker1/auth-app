package com.example.authjwt.user;

import com.example.authjwt.security.JwtAuthenticationFilter.JwtService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.io.IOException;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class UserController {
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final UserExportService userExportService;
    private final UserDetailsService userDetailsService;
    private final JwtService jwtService;

    public UserController(UserRepository userRepository, PasswordEncoder passwordEncoder,
                          UserExportService userExportService, UserDetailsService userDetailsService,
                          JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.userExportService = userExportService;
        this.userDetailsService = userDetailsService;
        this.jwtService = jwtService;
    }

    @GetMapping("/me")
    public MeResponse me(Authentication authentication) {
        User user = userRepository.findByEmail(authentication.getName())
                .orElseThrow();
        return new MeResponse(user.getFullName(), user.getEmail(), user.getRole(), user.getPhoto() != null);
    }

    @PutMapping(value = "/me", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public MeUpdateResponse updateMe(@Valid @RequestPart("data") UpdateMeRequest request,
                                      @RequestPart(value = "photo", required = false) MultipartFile photo,
                                      Authentication authentication) throws IOException {
        User user = userRepository.findByEmail(authentication.getName()).orElseThrow();
        String email = normalize(request.email());
        userRepository.findByEmail(email).filter(existing -> !existing.getId().equals(user.getId()))
                .ifPresent(existing -> { throw new ResponseStatusException(
                        HttpStatus.CONFLICT, "Cet email est déjà utilisé"); });
        user.setFullName(request.fullName().trim());
        user.setEmail(email);
        if (request.password() != null && !request.password().isBlank()) {
            user.setPassword(passwordEncoder.encode(request.password()));
        }
        if (photo != null && !photo.isEmpty()) {
            user.setPhoto(photo.getBytes());
            user.setPhotoContentType(photo.getContentType());
        }
        User saved = userRepository.save(user);
        String token = jwtService.generateToken(userDetailsService.loadUserByUsername(saved.getEmail()));
        return new MeUpdateResponse(saved.getFullName(), saved.getEmail(), saved.getRole(), saved.getPhoto() != null, token);
    }

    @GetMapping("/me/photo")
    public ResponseEntity<byte[]> myPhoto(Authentication authentication) {
        User user = userRepository.findByEmail(authentication.getName())
                .orElseThrow();
        if (user.getPhoto() == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Aucune photo");
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(user.getPhotoContentType() != null
                ? MediaType.parseMediaType(user.getPhotoContentType()) : MediaType.APPLICATION_OCTET_STREAM);
        return new ResponseEntity<>(user.getPhoto(), headers, HttpStatus.OK);
    }

    @GetMapping("/users")
    @PreAuthorize("hasRole('ADMIN')")
    public List<UserResponse> findAll() {
        return userRepository.findAll().stream().map(UserResponse::from).toList();
    }

    @GetMapping("/users/export/pdf")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<byte[]> exportPdf() {
        return exportResponse(userExportService.exportPdf(), MediaType.APPLICATION_PDF, "utilisateurs.pdf");
    }

    @GetMapping("/users/export/excel")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<byte[]> exportExcel() {
        MediaType excelType = MediaType.parseMediaType(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        return exportResponse(userExportService.exportExcel(), excelType, "utilisateurs.xlsx");
    }

    @PostMapping(value = "/users", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasRole('ADMIN')")
    public UserResponse create(@Valid @RequestPart("data") CreateUserRequest request,
                                @RequestPart(value = "photo", required = false) MultipartFile photo)
            throws IOException {
        String email = normalize(request.email());
        if (userRepository.existsByEmail(email)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Cet email est déjà utilisé");
        }
        User user = new User(request.fullName().trim(), email,
                passwordEncoder.encode(request.password()), normalizeRole(request.role()));
        if (photo != null && !photo.isEmpty()) {
            user.setPhoto(photo.getBytes());
            user.setPhotoContentType(photo.getContentType());
        }
        return UserResponse.from(userRepository.save(user));
    }

    @GetMapping("/users/{id}/photo")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<byte[]> userPhoto(@PathVariable Long id) {
        User user = userRepository.findById(id).orElseThrow(this::notFound);
        if (user.getPhoto() == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Aucune photo");
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(user.getPhotoContentType() != null
                ? MediaType.parseMediaType(user.getPhotoContentType()) : MediaType.APPLICATION_OCTET_STREAM);
        return new ResponseEntity<>(user.getPhoto(), headers, HttpStatus.OK);
    }

    @PutMapping("/users/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public UserResponse update(@PathVariable Long id, @Valid @RequestBody UpdateUserRequest request) {
        User user = userRepository.findById(id).orElseThrow(this::notFound);
        String email = normalize(request.email());
        userRepository.findByEmail(email).filter(existing -> !existing.getId().equals(id))
                .ifPresent(existing -> { throw new ResponseStatusException(
                        HttpStatus.CONFLICT, "Cet email est déjà utilisé"); });
        user.setFullName(request.fullName().trim());
        user.setEmail(email);
        user.setRole(normalizeRole(request.role()));
        if (request.password() != null && !request.password().isBlank()) {
            user.setPassword(passwordEncoder.encode(request.password()));
        }
        return UserResponse.from(userRepository.save(user));
    }

    @DeleteMapping("/users/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public void delete(@PathVariable Long id) {
        if (!userRepository.existsById(id)) {
            throw notFound();
        }
        userRepository.deleteById(id);
    }

    private String normalize(String email) {
        return email.trim().toLowerCase(java.util.Locale.ROOT);
    }

    private String normalizeRole(String role) {
        return role == null || role.isBlank() ? "USER" : role.trim().toUpperCase(java.util.Locale.ROOT);
    }

    private ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Utilisateur introuvable");
    }

    private ResponseEntity<byte[]> exportResponse(byte[] content, MediaType mediaType, String filename) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(mediaType);
        headers.setContentDisposition(ContentDisposition.attachment().filename(filename).build());
        return new ResponseEntity<>(content, headers, HttpStatus.OK);
    }
}

record MeResponse(String fullName, String email, String role, boolean hasPhoto) {
}

record MeUpdateResponse(String fullName, String email, String role, boolean hasPhoto, String token) {
}

record UpdateMeRequest(
        @NotBlank @Size(max = 255) String fullName,
        @Email @NotBlank String email,
        @Size(min = 8, max = 100) String password) {
}

record UserResponse(Long id, String fullName, String email, String role, boolean hasPhoto) {
    static UserResponse from(User user) {
        return new UserResponse(user.getId(), user.getFullName(), user.getEmail(), user.getRole(), user.getPhoto() != null);
    }
}

record CreateUserRequest(
        @NotBlank @Size(max = 255) String fullName,
        @Email @NotBlank String email,
        @NotBlank @Size(min = 8, max = 100) String password,
        String role) {
}

record UpdateUserRequest(
        @NotBlank @Size(max = 255) String fullName,
        @Email @NotBlank String email,
        @Size(min = 8, max = 100) String password,
        String role) {
}
// Retourne le nom et l'email de l'utilisateur connecté.
// #sert principalement à fournir les informations du profil de l'utilisateur connecté au frontend.
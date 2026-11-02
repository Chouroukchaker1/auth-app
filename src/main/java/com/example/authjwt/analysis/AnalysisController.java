package com.example.authjwt.analysis;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.security.core.Authentication;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

/**
 * Document analysis: forwards to the local Python service (document-analysis/api.py).
 * Only logged-in users get here, and each one only sees the analyses they started.
 */
@RestController
@RequestMapping("/api/analyses")
public class AnalysisController {
    private static final int MAX_TRACKED = 500;

    private final RestClient client;
    private final ObjectMapper objectMapper;
    private final Map<String, String> owners = new ConcurrentHashMap<>();

    public AnalysisController(@Value("${app.ocr.url}") String ocrUrl, ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5_000);
        factory.setReadTimeout(60_000);
        this.client = RestClient.builder().baseUrl(ocrUrl).requestFactory(factory).build();
        this.objectMapper = objectMapper;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<byte[]> start(@RequestPart("file") MultipartFile file, Authentication authentication) throws IOException {
        String filename = file.getOriginalFilename() == null ? "document" : file.getOriginalFilename();
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new ByteArrayResource(file.getBytes()) {
            @Override
            public String getFilename() { return filename; }
        });
        ResponseEntity<byte[]> response = forward(client.post().uri("/analyses")
                .contentType(MediaType.MULTIPART_FORM_DATA).body(body));
        if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
            if (owners.size() >= MAX_TRACKED) owners.clear();
            owners.put(objectMapper.readTree(response.getBody()).path("id").asText(), authentication.getName());
        }
        return response;
    }

    @GetMapping("/{id}")
    public ResponseEntity<byte[]> status(@PathVariable String id, Authentication authentication) {
        checkOwner(id, authentication);
        return forward(client.get().uri("/analyses/{id}", id));
    }

    @GetMapping("/{id}/page")
    public ResponseEntity<byte[]> page(@PathVariable String id, Authentication authentication) {
        checkOwner(id, authentication);
        return forward(client.get().uri("/analyses/{id}/page", id));
    }

    /** Member-form values recomputed from a result corrected by hand. */
    @PostMapping(value = "/member-form", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> memberForm(@RequestBody byte[] result) {
        return forward(client.post().uri("/member-form").contentType(MediaType.APPLICATION_JSON).body(result));
    }

    private void checkOwner(String id, Authentication authentication) {
        if (!authentication.getName().equals(owners.get(id))) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Analyse introuvable");
        }
    }

    /** Sends the request and hands back the service's status, type and body unchanged. */
    private ResponseEntity<byte[]> forward(RestClient.RequestHeadersSpec<?> request) {
        try {
            return request.exchange((req, res) -> {
                MediaType type = res.getHeaders().getContentType();
                return ResponseEntity.status(res.getStatusCode())
                        .contentType(type != null ? type : MediaType.APPLICATION_JSON)
                        .body(res.getBody().readAllBytes());
            });
        } catch (ResourceAccessException exception) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Le service d'analyse de document n'est pas démarré (document-analysis : python api.py)");
        }
    }
}

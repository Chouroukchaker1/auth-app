package com.example.authjwt.member;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MemberRepository extends JpaRepository<Member, Long> {
    Optional<Member> findByUserId(Long userId);
    boolean existsByUserId(Long userId);
    Optional<Member> findByNumeroUnifie(String numeroUnifie);
    Optional<Member> findByNomPrenom(String nomPrenom);
    boolean existsByNumeroUnifie(String numeroUnifie);
    boolean existsByNomPrenom(String nomPrenom);
}

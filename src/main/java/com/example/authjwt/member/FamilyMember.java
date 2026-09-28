package com.example.authjwt.member;

import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDate;

@Entity
@Table(name = "member_family")
public class FamilyMember {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id")
    private Member member;

    private String nom;
    private String prenom;
    private String lienParente;
    private LocalDate dateNaissance;

    protected FamilyMember() {
    }

    public FamilyMember(Member member, String nom, String prenom, String lienParente, LocalDate dateNaissance) {
        this.member = member;
        this.nom = nom;
        this.prenom = prenom;
        this.lienParente = lienParente;
        this.dateNaissance = dateNaissance;
    }

    public Long getId() { return id; }
    public Member getMember() { return member; }
    public String getNom() { return nom; }
    public String getPrenom() { return prenom; }
    public String getLienParente() { return lienParente; }
    public LocalDate getDateNaissance() { return dateNaissance; }
}

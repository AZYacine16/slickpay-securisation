// test/EvidenceRegistry.test.js
// Démontre le contrôle d'accès onlyOwner du registre de preuves.
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("EvidenceRegistry — contrôle d'accès onlyOwner", function () {
  let registry, owner, autre;

  // Un hash SHA-256 valide fait exactement 64 caractères hexadécimaux.
  const HASH_VALIDE = "a".repeat(64);

  beforeEach(async function () {
    [owner, autre] = await ethers.getSigners();
    const Registry = await ethers.getContractFactory("EvidenceRegistry");
    registry = await Registry.deploy();
    await registry.waitForDeployment();
  });

  it("désigne le déployeur comme propriétaire", async function () {
    expect(await registry.owner()).to.equal(owner.address);
  });

  it("autorise le propriétaire à enregistrer une preuve", async function () {
    await registry.addEvidence("siem_alerts.jsonl", "mini-siem", HASH_VALIDE);
    expect(await registry.getEvidenceCount()).to.equal(1);
  });

  it("rejette une écriture par un compte non autorisé", async function () {
    await expect(
      registry.connect(autre).addEvidence("faux.txt", "attaque", HASH_VALIDE)
    ).to.be.revertedWith("Acces refuse : reserve au proprietaire");

    // Le registre reste vide : aucune preuve parasite n'a été insérée.
    expect(await registry.getEvidenceCount()).to.equal(0);
  });

  it("permet à tous de lire et vérifier une preuve existante", async function () {
    await registry.addEvidence("siem_summary.txt", "mini-siem", HASH_VALIDE);
    // Lecture par un autre compte que le propriétaire : autorisée.
    const valide = await registry.connect(autre).verifyEvidence(0, HASH_VALIDE);
    expect(valide).to.equal(true);
  });

  it("transfère la propriété puis autorise le nouveau propriétaire", async function () {
    await registry.transferOwnership(autre.address);
    expect(await registry.owner()).to.equal(autre.address);
    // L'ancien propriétaire ne peut plus écrire.
    await expect(
      registry.addEvidence("x.txt", "type", HASH_VALIDE)
    ).to.be.revertedWith("Acces refuse : reserve au proprietaire");
    // Le nouveau, si.
    await registry.connect(autre).addEvidence("ok.txt", "type", HASH_VALIDE);
    expect(await registry.getEvidenceCount()).to.equal(1);
  });
});

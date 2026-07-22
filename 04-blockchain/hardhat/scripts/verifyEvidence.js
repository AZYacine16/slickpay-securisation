const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function sha256File(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(fileBuffer).digest("hex");
}

async function main() {
  const baseDir = path.join(__dirname, "..", "..");
  const logsDir = path.join(baseDir, "logs");

  const addressPath = path.join(logsDir, "hardhat_contract_address.txt");
  const registeredPath = path.join(logsDir, "hardhat_registered_evidence.json");

  if (!fs.existsSync(addressPath)) {
    throw new Error("Contract address not found.");
  }

  if (!fs.existsSync(registeredPath)) {
    throw new Error("Registered evidence file not found.");
  }

  const contractAddress = fs.readFileSync(addressPath, "utf8").trim();
  const registry = await ethers.getContractAt("EvidenceRegistry", contractAddress);

  const registeredData = JSON.parse(fs.readFileSync(registeredPath, "utf8"));
  const results = [];

  let globalStatus = true;

  for (const evidence of registeredData.registeredEvidence) {
    const absolutePath = path.join(baseDir, evidence.sourcePath);

    if (!fs.existsSync(absolutePath)) {
      globalStatus = false;

      results.push({
        evidenceId: evidence.evidenceId,
        fileName: evidence.fileName,
        status: "INVALID",
        reason: "Source file not found"
      });

      continue;
    }

    const currentHash = sha256File(absolutePath);
    const isValid = await registry.verifyEvidence(evidence.evidenceId, currentHash);

    if (!isValid) {
      globalStatus = false;
    }

    results.push({
      evidenceId: evidence.evidenceId,
      fileName: evidence.fileName,
      sourcePath: evidence.sourcePath,
      originalHash: evidence.sha256,
      currentHash: currentHash,
      status: isValid ? "VALID" : "INVALID"
    });

    console.log(`${isValid ? "[OK]" : "[ERROR]"} ${evidence.fileName} => ${isValid ? "VALID" : "INVALID"}`);
  }

  const reportLines = [];

  reportLines.push("=== Vérification blockchain Hardhat ===");
  reportLines.push("");
  reportLines.push(`Date de vérification : ${new Date().toISOString()}`);
  reportLines.push(`Contrat : ${contractAddress}`);
  reportLines.push("");
  reportLines.push("Résultat global :");
  reportLines.push(globalStatus ? "VALIDÉ" : "INVALIDE");
  reportLines.push("");
  reportLines.push("Détails :");

  for (const result of results) {
    reportLines.push(`- ${result.fileName} : ${result.status}`);

    if (result.originalHash) {
      reportLines.push(`  Hash initial : ${result.originalHash}`);
      reportLines.push(`  Hash actuel  : ${result.currentHash}`);
    }

    if (result.reason) {
      reportLines.push(`  Raison : ${result.reason}`);
    }
  }

  reportLines.push("");
  reportLines.push("Conclusion :");
  reportLines.push(
    globalStatus
      ? "Les empreintes SHA-256 recalculées correspondent aux empreintes enregistrées dans le smart contract."
      : "Une différence a été détectée entre les fichiers actuels et les empreintes enregistrées dans le smart contract."
  );

  fs.writeFileSync(
    path.join(logsDir, "hardhat_verification.txt"),
    reportLines.join("\n")
  );

  fs.writeFileSync(
    path.join(logsDir, "hardhat_verification.json"),
    JSON.stringify(
      {
        checkedAt: new Date().toISOString(),
        contractAddress: contractAddress,
        globalStatus: globalStatus ? "VALID" : "INVALID",
        results: results
      },
      null,
      2
    )
  );

  console.log("[OK] Verification report written to logs/hardhat_verification.txt");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

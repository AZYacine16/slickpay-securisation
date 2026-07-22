const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const evidenceFiles = [
  { path: "logs/siem_alerts.jsonl", evidenceType: "MINI_SIEM_ALERTS" },
  { path: "logs/siem_summary.txt", evidenceType: "MINI_SIEM_SUMMARY" },
  { path: "logs/wazuh_compose_ps.txt", evidenceType: "WAZUH_PROOF" },
  { path: "logs/wazuh_dashboard_logs.txt", evidenceType: "WAZUH_PROOF" },
  { path: "logs/wazuh_indexer_logs.txt", evidenceType: "WAZUH_PROOF" },
  { path: "logs/wazuh_manager_logs.txt", evidenceType: "WAZUH_PROOF" },
  { path: "logs/wazuh_disk_state.txt", evidenceType: "WAZUH_PROOF" }
];

function sha256File(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(fileBuffer).digest("hex");
}

async function main() {
  const baseDir = path.join(__dirname, "..", "..");
  const logsDir = path.join(baseDir, "logs");

  const addressPath = path.join(logsDir, "hardhat_contract_address.txt");

  if (!fs.existsSync(addressPath)) {
    throw new Error("Contract address not found. Run deploy.js first.");
  }

  const contractAddress = fs.readFileSync(addressPath, "utf8").trim();
  const registry = await ethers.getContractAt("EvidenceRegistry", contractAddress);

  const registeredEvidence = [];
  const missingFiles = [];

  for (const evidence of evidenceFiles) {
    const absolutePath = path.join(baseDir, evidence.path);

    if (!fs.existsSync(absolutePath)) {
      missingFiles.push({
        file: evidence.path,
        reason: "File not found"
      });
      continue;
    }

    const hash = sha256File(absolutePath);
    const fileName = path.basename(evidence.path);

    const tx = await registry.addEvidence(
      fileName,
      evidence.evidenceType,
      hash
    );

    const receipt = await tx.wait();
    const count = await registry.getEvidenceCount();
    const evidenceId = Number(count) - 1;

    registeredEvidence.push({
      evidenceId: evidenceId,
      fileName: fileName,
      sourcePath: evidence.path,
      evidenceType: evidence.evidenceType,
      sha256: hash,
      transactionHash: receipt.hash || receipt.transactionHash,
      blockNumber: Number(receipt.blockNumber)
    });

    console.log(`[OK] Registered ${fileName}`);
    console.log(`     SHA-256: ${hash}`);
    console.log(`     TX: ${receipt.hash || receipt.transactionHash}`);
  }

  const output = {
    project: "SlickPay blockchain Hardhat PoC",
    contractAddress: contractAddress,
    registeredAt: new Date().toISOString(),
    registeredEvidence: registeredEvidence,
    missingFiles: missingFiles,
    privacyNote: "Only SHA-256 hashes and minimal metadata are stored on-chain. Original logs are not stored in the smart contract."
  };

  fs.writeFileSync(
    path.join(logsDir, "hardhat_registered_evidence.json"),
    JSON.stringify(output, null, 2)
  );

  console.log("[OK] Evidence registration proof written to logs/hardhat_registered_evidence.json");

  if (missingFiles.length > 0) {
    console.log("[INFO] Some files were missing. Check hardhat_registered_evidence.json");
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

const fs = require("fs");
const path = require("path");

async function main() {
  const EvidenceRegistry = await ethers.getContractFactory("EvidenceRegistry");
  const registry = await EvidenceRegistry.deploy();

  if (registry.waitForDeployment) {
    await registry.waitForDeployment();
  } else {
    await registry.deployed();
  }

  const contractAddress = registry.getAddress
    ? await registry.getAddress()
    : registry.address;

  const logsDir = path.join(__dirname, "..", "..", "logs");
  fs.mkdirSync(logsDir, { recursive: true });

  const deploymentProof = {
    project: "SlickPay blockchain Hardhat PoC",
    contractName: "EvidenceRegistry",
    contractAddress: contractAddress,
    deployedAt: new Date().toISOString(),
    network: "localhost",
    purpose: "Register SHA-256 hashes of Mini-SIEM and Wazuh evidence files"
  };

  fs.writeFileSync(
    path.join(logsDir, "hardhat_deployment.json"),
    JSON.stringify(deploymentProof, null, 2)
  );

  fs.writeFileSync(
    path.join(logsDir, "hardhat_contract_address.txt"),
    contractAddress
  );

  console.log("[OK] EvidenceRegistry deployed");
  console.log("[OK] Contract address:", contractAddress);
  console.log("[OK] Deployment proof written to logs/hardhat_deployment.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

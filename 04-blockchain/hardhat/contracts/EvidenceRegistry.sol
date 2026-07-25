// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

contract EvidenceRegistry {
    // Propriétaire du registre : seule identité autorisée à enregistrer des preuves.
    address public owner;

    struct Evidence {
        uint256 id;
        string fileName;
        string evidenceType;
        string fileHash;
        uint256 timestamp;
        address submitter;
    }

    Evidence[] private evidences;

    event EvidenceAdded(
        uint256 indexed id,
        string fileName,
        string evidenceType,
        string fileHash,
        uint256 timestamp,
        address indexed submitter
    );

    // Émis lors d'un transfert de propriété du registre.
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // Le déployeur du contrat devient le propriétaire initial.
    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    // Restreint l'exécution d'une fonction au seul propriétaire.
    modifier onlyOwner() {
        require(msg.sender == owner, "Acces refuse : reserve au proprietaire");
        _;
    }

    function addEvidence(
        string memory _fileName,
        string memory _evidenceType,
        string memory _fileHash
    ) public onlyOwner {
        require(bytes(_fileName).length > 0, "File name is required");
        require(bytes(_evidenceType).length > 0, "Evidence type is required");
        require(bytes(_fileHash).length == 64, "SHA-256 hash must be 64 hex characters");

        uint256 evidenceId = evidences.length;

        evidences.push(
            Evidence({
                id: evidenceId,
                fileName: _fileName,
                evidenceType: _evidenceType,
                fileHash: _fileHash,
                timestamp: block.timestamp,
                submitter: msg.sender
            })
        );

        emit EvidenceAdded(
            evidenceId,
            _fileName,
            _evidenceType,
            _fileHash,
            block.timestamp,
            msg.sender
        );
    }

    // Transfère la propriété du registre à une nouvelle adresse.
    function transferOwnership(address _newOwner) public onlyOwner {
        require(_newOwner != address(0), "Nouveau proprietaire invalide");
        emit OwnershipTransferred(owner, _newOwner);
        owner = _newOwner;
    }

    function getEvidence(uint256 _id) public view returns (
        uint256 id,
        string memory fileName,
        string memory evidenceType,
        string memory fileHash,
        uint256 timestamp,
        address submitter
    ) {
        require(_id < evidences.length, "Evidence does not exist");

        Evidence memory evidence = evidences[_id];

        return (
            evidence.id,
            evidence.fileName,
            evidence.evidenceType,
            evidence.fileHash,
            evidence.timestamp,
            evidence.submitter
        );
    }

    function getEvidenceCount() public view returns (uint256) {
        return evidences.length;
    }

    function verifyEvidence(uint256 _id, string memory _currentHash) public view returns (bool) {
        require(_id < evidences.length, "Evidence does not exist");

        return keccak256(bytes(evidences[_id].fileHash)) == keccak256(bytes(_currentHash));
    }
}

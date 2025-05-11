// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/**
 * @title Faucet
 * @dev Contract to distribute testnet SEI and USDT tokens with cooldown periods
 * Supports both direct claims and gasless claims via meta-transactions
 */
contract Faucet is Ownable {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // Token constants
    IERC20 public usdtToken;
    
    // Distribution amounts
    uint256 public seiAmount = 0.5 ether; // 0.5 SEI
    uint256 public usdtAmount = 3000 * 10**6; // 3000 USDT assuming 6 decimals
    
    // Cooldown period in seconds (3 hours = 10800 seconds)
    uint256 public cooldownPeriod = 3 hours;
    
    // Token types
    uint8 public constant SEI = 0;
    uint8 public constant USDT = 1;
    
    // Mapping to track when user can claim again
    mapping(address => mapping(uint8 => uint256)) public nextClaimTime;
    
    // Mapping to track used nonces for meta-transactions
    mapping(address => mapping(uint256 => bool)) public usedNonces;

    // Address of the relay server that pays for gas
    address public relayer;
    
    // Events
    event TokensClaimed(address indexed user, uint8 tokenType, uint256 amount, bool isGasless);
    event FaucetFunded(address indexed funder, uint8 tokenType, uint256 amount);
    event AmountsUpdated(uint256 newSeiAmount, uint256 newUsdtAmount);
    event CooldownUpdated(uint256 newCooldown);
    event RelayerUpdated(address newRelayer);
    
    /**
     * @dev Constructor that sets the USDT token address and initial relayer
     * @param _usdtToken The USDT token contract address
     */
    constructor(address _usdtToken) Ownable(msg.sender) {
        usdtToken = IERC20(_usdtToken);
        relayer = msg.sender; // Initially set relayer to deployer
    }
    
    /**
     * @dev Allows users to claim SEI tokens with cooldown
     */
    function claimSEI() external {
        _claimSEI(msg.sender);
    }
    
    /**
     * @dev Allows users to claim USDT tokens with cooldown
     */
    function claimUSDT() external {
        _claimUSDT(msg.sender);
    }
    
    /**
     * @dev Internal function to handle SEI claims
     * @param recipient The address receiving SEI tokens
     */
    function _claimSEI(address recipient) internal {
        require(block.timestamp >= nextClaimTime[recipient][SEI], "Cooldown period not over yet");
        require(address(this).balance >= seiAmount, "Insufficient SEI balance in faucet");
        
        // Update next claim time
        nextClaimTime[recipient][SEI] = block.timestamp + cooldownPeriod;
        
        // Transfer SEI to user
        (bool sent, ) = payable(recipient).call{value: seiAmount}("");
        require(sent, "Failed to send SEI");
        
        emit TokensClaimed(recipient, SEI, seiAmount, msg.sender == relayer);
    }
    
    /**
     * @dev Internal function to handle USDT claims
     * @param recipient The address receiving USDT tokens
     */
    function _claimUSDT(address recipient) internal {
        require(block.timestamp >= nextClaimTime[recipient][USDT], "Cooldown period not over yet");
        require(usdtToken.balanceOf(address(this)) >= usdtAmount, "Insufficient USDT balance in faucet");
        
        // Update next claim time
        nextClaimTime[recipient][USDT] = block.timestamp + cooldownPeriod;
        
        // Transfer USDT to user
        require(usdtToken.transfer(recipient, usdtAmount), "USDT transfer failed");
        
        emit TokensClaimed(recipient, USDT, usdtAmount, msg.sender == relayer);
    }

    /**
     * @dev Validates a signature for a meta-transaction
     * @param user Address of the user
     * @param tokenType Type of token to claim (0 = SEI, 1 = USDT)
     * @param nonce Unique number to prevent replay attacks
     * @param signature Signature data
     * @return True if signature is valid
     */
    function _validateSignature(address user, uint8 tokenType, uint256 nonce, bytes memory signature) internal view returns (bool) {
        // Create the hash that was signed
        bytes32 messageHash = keccak256(abi.encodePacked(address(this), user, tokenType, nonce));
        
        // Convert to an Ethereum signed message hash (adds the "\x19Ethereum Signed Message:\n32" prefix)
        bytes32 ethSignedMessageHash = messageHash.toEthSignedMessageHash();
        
        // Recover the signer address and verify it matches the user
        address recoveredSigner = ECDSA.recover(ethSignedMessageHash, signature);
        return recoveredSigner == user;
    }

    /**
     * @dev Allows gasless claiming of SEI tokens via meta-transaction
     * @param user The user address that will receive tokens
     * @param nonce Unique number to prevent replay attacks
     * @param signature Signature proving user's consent
     */
    function claimSEIGasless(address user, uint256 nonce, bytes calldata signature) external {
        require(msg.sender == relayer, "Only relayer can execute gasless transactions");
        require(!usedNonces[user][nonce], "Nonce already used");
        require(_validateSignature(user, SEI, nonce, signature), "Invalid signature");
        
        usedNonces[user][nonce] = true;
        _claimSEI(user);
    }

    /**
     * @dev Allows gasless claiming of USDT tokens via meta-transaction
     * @param user The user address that will receive tokens
     * @param nonce Unique number to prevent replay attacks
     * @param signature Signature proving user's consent
     */
    function claimUSDTGasless(address user, uint256 nonce, bytes calldata signature) external {
        require(msg.sender == relayer, "Only relayer can execute gasless transactions");
        require(!usedNonces[user][nonce], "Nonce already used");
        require(_validateSignature(user, USDT, nonce, signature), "Invalid signature");
        
        usedNonces[user][nonce] = true;
        _claimUSDT(user);
    }

    /**
     * @dev Set a new relayer address
     * @param newRelayer Address of the new relayer
     */
    function setRelayer(address newRelayer) external onlyOwner {
        require(newRelayer != address(0), "Relayer cannot be zero address");
        relayer = newRelayer;
        emit RelayerUpdated(newRelayer);
    }

    /**
     * @dev Check if a nonce has been used for a user
     * @param user The user address
     * @param nonce The nonce to check
     * @return True if the nonce has been used
     */
    function isNonceUsed(address user, uint256 nonce) external view returns (bool) {
        return usedNonces[user][nonce];
    }
    
    /**
     * @dev Returns the timestamp when a user can claim a specific token again
     * @param user The user address
     * @param tokenType 0 for SEI, 1 for USDT
     * @return Next claim timestamp
     */
    function getNextClaimTime(address user, uint8 tokenType) external view returns (uint256) {
        return nextClaimTime[user][tokenType];
    }
    
    /**
     * @dev Returns the SEI balance of a user
     * @param user The user address
     * @return SEI balance
     */
    function getSEIBalance(address user) external view returns (uint256) {
        return user.balance;
    }
    
    /**
     * @dev Returns the USDT balance of a user
     * @param user The user address
     * @return USDT balance
     */
    function getUSDTBalance(address user) external view returns (uint256) {
        return usdtToken.balanceOf(user);
    }
    
    /**
     * @dev Owner can fund the faucet with SEI
     */
    function fundSEI() external payable onlyOwner {
        emit FaucetFunded(msg.sender, SEI, msg.value);
    }
    
    /**
     * @dev Owner can fund the faucet with USDT
     * @param amount The amount of USDT to deposit
     */
    function fundUSDT(uint256 amount) external onlyOwner {
        require(usdtToken.transferFrom(msg.sender, address(this), amount), "USDT transfer failed");
        emit FaucetFunded(msg.sender, USDT, amount);
    }
    
    /**
     * @dev Owner can update distribution amounts
     * @param newSeiAmount New SEI amount to distribute
     * @param newUsdtAmount New USDT amount to distribute
     */
    function updateAmounts(uint256 newSeiAmount, uint256 newUsdtAmount) external onlyOwner {
        seiAmount = newSeiAmount;
        usdtAmount = newUsdtAmount;
        emit AmountsUpdated(newSeiAmount, newUsdtAmount);
    }
    
    /**
     * @dev Owner can update the cooldown period
     * @param newCooldown New cooldown period in seconds
     */
    function updateCooldown(uint256 newCooldown) external onlyOwner {
        cooldownPeriod = newCooldown;
        emit CooldownUpdated(newCooldown);
    }
    
    /**
     * @dev Fallback function to receive SEI
     */
    receive() external payable {}
}
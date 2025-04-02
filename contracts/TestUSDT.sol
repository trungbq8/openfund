// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title TestUSDT
 * @dev A test USDT token for testing the OpenFund contract
 * This token uses 6 decimals
 */
contract TestUSDT is ERC20, Ownable {
    uint8 private _decimals = 6;

    constructor() ERC20("Test USDT", "USDT") Ownable(msg.sender) {
        // Mint 1 million test USDT to deployer
        _mint(msg.sender, 1_000_000 * 10**_decimals);
    }

    /**
     * @dev Returns the number of decimals used to get its user representation
     */
    function decimals() public view virtual override returns (uint8) {
        return _decimals;
    }

    /**
     * @dev Mint additional tokens to a specific address (only owner)
     * @param to Address to mint tokens to
     * @param amount Amount of tokens to mint
     */
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    /**
     * @dev Allows users to request test tokens (faucet functionality)
     * Limits to 10,000 USDT per request
     */
    function requestTokens() external {
        uint256 amount = 10_000 * 10**_decimals; // 10,000 USDT
        _mint(msg.sender, amount);
    }
}
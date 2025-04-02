// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title TestUSDT
 * @dev Test USDT token for testing the fundraising contract
 */
contract TestUSDT is ERC20, Ownable {
    uint8 private _decimals = 6;

    constructor() ERC20("Test USDT", "USDT") Ownable(msg.sender) {
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
     * @dev Allows users to request test tokens
     */
    function requestTokens() external {
        uint256 amount = 10_000 * 10**_decimals;
        _mint(msg.sender, amount);
    }
}
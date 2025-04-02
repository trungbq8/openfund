// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract TestProjectToken is ERC20, Ownable {
    uint8 private _decimals = 18;
    
    uint256 private constant INITIAL_SUPPLY = 1_000_000_000 * (10 ** 18);

    constructor() ERC20("Test Project Token", "TPT") Ownable(msg.sender) {
        _mint(msg.sender, INITIAL_SUPPLY);
    }

    function decimals() public view virtual override returns (uint8) {
        return _decimals;
    }

    function burn(uint256 amount) public {
        _burn(msg.sender, amount);
    }

    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }
}
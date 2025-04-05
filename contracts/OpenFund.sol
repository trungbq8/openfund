// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract OpenFund is Ownable, ReentrancyGuard {
    uint256 public constant USDT_UNIT = 100 * 10**6; // USDT decimal 6
    uint256 public constant MAX_INVESTMENT_UNITS = 10;
    uint256 public constant PLATFORM_FEE_PERCENT = 5;
    uint256 public constant VOTING_PERIOD = 3 days;

    enum ProjectStatus { InitialCreated, RaisingPeriod, VotingPeriod, FundingFailed, FundingCompleted }

    struct Project {
        uint256 id;
        address raiser;
        address tokenAddress;
        uint256 tokensToSell;
        uint256 tokenPrice; // Use decimal 6
        uint256 endFundingTime;
        uint256 endVotingTime;
        uint256 endRefundTime;
        uint256 fundsRaised;
        uint256 tokensSold;
        uint8 decimal;
        bool fundsClaimed;
        bool platformFeeClaimed;
        mapping(address => uint256) investments;
        mapping(address => bool) hasVoted;
        mapping(address => bool) refundClaimed;
        mapping(address => bool) rejectFundRelease;
        uint256 voteForRefund;
        uint256 investorsCount;
        uint256 votersForRefundCount;
        ProjectStatus status;
    }
    
    // USDT token address
    IERC20 public usdtToken;
    
    // Project storage
    mapping(uint256 => Project) private projects;

    mapping(address => uint256[]) private investorProjects;
    
    // Events
    event ProjectCreated(uint256 indexed projectId, address indexed raiser, uint256 tokensToSell, uint256 tokenPrice, uint256 endFundingTime);
    event TokensDeposited(uint256 indexed projectId, uint256 amount);
    event InvestmentMade(uint256 indexed projectId, address indexed investor, uint256 amount, uint256 tokensToReceive);
    event VoteCast(uint256 indexed projectId, address indexed voter);
    event FundsClaimed(uint256 indexed projectId, uint256 amount);
    event TokensClaimed(uint256 indexed projectId, address indexed investor, uint256 amount);
    event Refunded(uint256 indexed projectId, address indexed investor, uint256 amount);
    event UnsoldTokensClaimed(uint256 indexed projectId, uint256 amount);
    event PlatformFeeClaimed(uint256 indexed projectId, uint256 amount);
    event ProjectFailed(uint256 projectId);

    constructor(address _usdtAddress) Ownable(msg.sender) {
        usdtToken = IERC20(_usdtAddress);
    }
    
    /**
     * @dev Create a new project
     * @param _projectId Id of project
     * @param _raiser Address of the project owner
     * @param _tokenAddress Address of the project token
     * @param _tokensToSell Amount of tokens to sell
     * @param _tokenPrice Price per token in USDT
     * @param _endFundingTime Timestamp when the funding period ends
     */
    function createProject(
        uint256 _projectId,
        address _raiser,
        address _tokenAddress,
        uint256 _tokensToSell,
        uint256 _tokenPrice,
        uint256 _endFundingTime,
        uint8 _decimal
    ) external onlyOwner {
        
        require(_endFundingTime > block.timestamp, "End time must be in the future");
        require(_tokensToSell > 0, "Tokens to sell must be greater than 0");
        require(_raiser != address(0), "Invalid raiser address");
        require(_tokenAddress != address(0), "Invalid token address");
        
        Project storage project = projects[_projectId];

        uint8 projectTokenDecimal = IERC20Metadata(_tokenAddress).decimals();
        require(projectTokenDecimal == _decimal, "Invalid token address");

        project.id = _projectId;
        project.raiser = _raiser;
        project.tokenAddress = _tokenAddress;
        project.tokensToSell = _tokensToSell;
        project.tokenPrice = _tokenPrice;
        project.endFundingTime = _endFundingTime;
        project.status = ProjectStatus.InitialCreated;
        project.platformFeeClaimed = false;
        project.fundsRaised = 0;
        project.endVotingTime = _endFundingTime + 3 days;
        project.endRefundTime = _endFundingTime + 4 days;
        project.decimal = projectTokenDecimal;
        
        emit ProjectCreated(_projectId, _raiser, _tokensToSell, _tokenPrice, _endFundingTime);
    }
    
    /**
     * @dev Raiser deposits tokens to be sold
     * @param _projectId ID of the project
     */
    function depositTokens(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(msg.sender == project.raiser, "Only raiser can deposit tokens");
        require(project.status != ProjectStatus.RaisingPeriod, "Tokens already deposited");
        require(block.timestamp < project.endFundingTime, "Project funding period has ended");
        
        IERC20 projectToken = IERC20(project.tokenAddress);
        uint256 tokenAmount = project.tokensToSell * 10**project.decimal;
        
        require(
            projectToken.transferFrom(msg.sender, address(this), tokenAmount),
            "Depositing: Token transfer failed"
        );
        
        project.status = ProjectStatus.RaisingPeriod;
        
        emit TokensDeposited(_projectId, tokenAmount);
    }
    
    /**
     * @dev User invests in a project
     * @param _projectId ID of the project
     * @param _units Number of units to invest (max 10 units, each unit is 100 USDT)
     */
    function invest(uint256 _projectId, uint256 _units) external nonReentrant {
        require(_units > 0 && _units <= MAX_INVESTMENT_UNITS, "Invalid units amount");
        
        Project storage project = projects[_projectId];
        
        require(project.status == ProjectStatus.RaisingPeriod, "It is not raising period");
        require(block.timestamp < project.endFundingTime, "Project funding period has ended");
        
        uint256 investedUnit = project.investments[msg.sender] / USDT_UNIT;
        require(investedUnit + _units <= MAX_INVESTMENT_UNITS, "Exceed maximum investment per project");

        uint256 newInvestmentAmount = _units * USDT_UNIT;
        uint256 tokensToReceive = newInvestmentAmount / project.tokenPrice;
        
        require(project.tokensSold + tokensToReceive <= project.tokensToSell, "Not enough tokens left");
        
        require(
            usdtToken.transferFrom(msg.sender, address(this), newInvestmentAmount),
            "Investing: USDT transfer failed"
        );
        
        if (project.investments[msg.sender] == 0) {
            project.investorsCount++;
            investorProjects[msg.sender].push(_projectId);
        }
        
        IERC20 projectToken = IERC20(project.tokenAddress);
        require(
            projectToken.transfer(msg.sender, tokensToReceive *10**project.decimal),
            "Token transfer to investor failed"
        );

        project.investments[msg.sender] += newInvestmentAmount;
        project.fundsRaised += newInvestmentAmount;
        project.tokensSold += tokensToReceive;
        
        emit InvestmentMade(_projectId, msg.sender, newInvestmentAmount, tokensToReceive);
    }
    
    /**
     * @dev User votes on a project
     * @param _projectId ID of the project
     */
    function voteForRefund(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(block.timestamp >= project.endFundingTime && block.timestamp <= project.endVotingTime, "Not in voting period");
        require(!project.hasVoted[msg.sender], "Already voted");
        
        // Check token balance for voting weight
        IERC20 projectToken = IERC20(project.tokenAddress);
        uint256 voterBalance = projectToken.balanceOf(msg.sender);
        require(voterBalance > 0, "Only token holders can vote");

        if (project.status == ProjectStatus.RaisingPeriod) {
            project.status = ProjectStatus.VotingPeriod;
        }

        project.hasVoted[msg.sender] = true;

        project.voteForRefund += voterBalance / 10**project.decimal;

        if (project.voteForRefund > project.tokensSold / 2) {
            project.status = ProjectStatus.FundingFailed;
            emit ProjectFailed(_projectId);
        }
        project.rejectFundRelease[msg.sender] == true;
        project.votersForRefundCount++;
        emit VoteCast(_projectId, msg.sender);
    }
    
    /**
     * @dev Raiser claims funds after successful funding and approval
     * @param _projectId ID of the project
     */
    function claimFunds(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(msg.sender == project.raiser, "Only raiser can claim funds");
        require(block.timestamp >= project.endRefundTime, "It is not time to claim fund");
        require(!project.fundsClaimed, "Funds already claimed");
        
        uint256 platformFee = (project.fundsRaised * PLATFORM_FEE_PERCENT) / 100;
        uint256 raiserAmount = project.fundsRaised - platformFee;
        
        require(
            usdtToken.transfer(project.raiser, raiserAmount),
            "USDT transfer to raiser failed"
        );
        
        project.fundsClaimed = true;

        if (project.status != ProjectStatus.FundingFailed){
            project.status = ProjectStatus.FundingCompleted;
        }

        emit FundsClaimed(_projectId, raiserAmount);
    }
    
    /**
     * @dev Investor gets refund if project is rejected
     * @param _projectId ID of the project
     */
    function getRefund(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        require(block.timestamp >= project.endVotingTime && block.timestamp <= project.endRefundTime, "Not in refund period");
        require(project.status == ProjectStatus.FundingFailed, "Project is not rejected");
        require(!project.refundClaimed[msg.sender], "Already claim refund");
        
        IERC20 projectToken = IERC20(project.tokenAddress);
        uint256 userTokenBalance = projectToken.balanceOf(msg.sender);
        require(userTokenBalance > 0, "Only tokens holder can get refund");

        uint256 refundAmount = (userTokenBalance / 10**project.decimal) * project.tokenPrice;
        
        require(
            usdtToken.transfer(msg.sender, refundAmount),
            "USDT refund failed"
        );

        require(
            projectToken.transferFrom(msg.sender, address(this), userTokenBalance),
            "Token transfer failed"
        );
        
        project.tokensSold -= userTokenBalance / 10**project.decimal;
        project.tokensToSell += userTokenBalance / 10**project.decimal;
        project.refundClaimed[msg.sender] = true;
        project.fundsRaised -= refundAmount;
        
        emit Refunded(_projectId, msg.sender, refundAmount);
    }
    /**
     * @dev Raiser claims unsold tokens
     * @param _projectId ID of the project
     */
    function claimUnsoldTokens(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(msg.sender == project.raiser, "Only raiser can claim unsold tokens");
        require(block.timestamp >= project.endRefundTime, "It is not time to claim unsold tokens");
        
        uint256 unsoldTokens = project.tokensToSell - project.tokensSold;
        require(unsoldTokens > 0, "No unsold tokens");
        
        // Transfer unsold tokens back to raiser
        IERC20 projectToken = IERC20(project.tokenAddress);
        require(
            projectToken.transfer(project.raiser, unsoldTokens * 10**project.decimal),
            "Token transfer failed"
        );
        
        emit UnsoldTokensClaimed(_projectId, unsoldTokens);
    }
    /**
     * @dev Platform claims fee
     * @param _projectId ID of the project
     */
    function claimPlatformFee(uint256 _projectId) external onlyOwner nonReentrant {
        Project storage project = projects[_projectId];
        
        require(block.timestamp >= project.endRefundTime, "It is not time to claim fee");
        require(project.status == ProjectStatus.FundingCompleted, "Project funding is failed");
        require(!project.platformFeeClaimed, "Platform fee already claimed");
        
        uint256 platformFee = (project.fundsRaised * PLATFORM_FEE_PERCENT) / 100;
        
        require(
            usdtToken.transfer(owner(), platformFee),
            "USDT transfer to platform failed"
        );

        project.platformFeeClaimed = true;
        
        emit PlatformFeeClaimed(_projectId, platformFee);
    }
    /**
    * @dev Get project details
    * @param _projectId ID of the project
    */
    function getProjectDetails(uint256 _projectId) external view returns (
        address raiser,
        address tokenAddress,
        uint256 tokensToSell,
        uint256 tokensSold,
        uint256 tokenPrice,
        uint256 endFundingTime,
        uint256 fundsRaised,
        ProjectStatus status,
        uint256 investorsCount,
        uint256 votersForRefundCount,
        uint256 voterForRefundPercentage
    ) {
        Project storage project = projects[_projectId];
        
        uint256 _voterForRefundPercentage = 0;
        if (project.fundsRaised > 0) {
            _voterForRefundPercentage = (project.voteForRefund * 100) / project.fundsRaised;
        }
        return (
            project.raiser,
            project.tokenAddress,
            project.tokensToSell,
            project.tokensSold,
            project.tokenPrice,
            project.endFundingTime,
            project.fundsRaised,
            project.status,
            project.investorsCount,
            project.votersForRefundCount,
            _voterForRefundPercentage
        );
    }
    
    /**
     * @dev Get investment details
     * @param _projectId ID of the project
     * @param _investor Address of the investor
     */
    function getInvestmentDetails(uint256 _projectId, address _investor) external view returns (
        uint256 investmentAmount,
        bool hasVoted,
        bool rejectFundRelease,
        bool hasClaimedRefund
    ) {
        Project storage project = projects[_projectId];
        
        return (
            project.investments[_investor],
            project.hasVoted[_investor],
            project.rejectFundRelease[_investor],
            project.refundClaimed[_investor]
        );
    }
    
    /**
     * @dev Get all projected invested of an investor
     * @param _investor Address of investor
     */
    function getInvestorProjects(address _investor) external view returns (uint256[] memory) {
        return investorProjects[_investor];
    }
}
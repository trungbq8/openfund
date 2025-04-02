// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract OpenFund is Ownable, ReentrancyGuard {
    uint256 public constant USDT_UNIT = 100 * 10**6;
    uint256 public constant MAX_INVESTMENT_UNITS = 10;
    uint256 public constant PLATFORM_FEE_PERCENT = 5;

    enum ProjectStatus { Created, Raising, Voting, Approved, Rejected, Completed }

    struct Project {
        uint256 id;
        address raiser;
        address tokenAddress;
        uint256 tokensToSell;
        uint256 tokenPrice;
        uint256 endTime;
        uint256 fundsRaised;
        uint256 tokensSold;
        bool fundsClaimed;
        bool platformFeeClaimed;
        mapping(address => uint256) investments;
        mapping(address => bool) hasVoted;
        mapping(address => bool) refundClaimed;
        mapping(address => bool) voteDecision;
        uint256 approvalVotes;
        uint256 rejectionVotes;
        uint256 investorsCount;
        uint256 votersCount;
        mapping(address => bool) hasClaimedTokens;
        ProjectStatus status;
        bool claimUnsoldToken;
    }
    
    IERC20 public usdtToken;
    
    mapping(uint256 => Project) private projects;

    mapping(address => uint256[]) private investorProjects;
    
    event ProjectCreated(uint256 indexed projectId, address indexed raiser, uint256 tokensToSell, uint256 tokenPrice, uint256 endTime);
    event TokensDeposited(uint256 indexed projectId, uint256 amount);
    event InvestmentMade(uint256 indexed projectId, address indexed investor, uint256 amount);
    event VoteCast(uint256 indexed projectId, address indexed voter, bool decision);
    event FundsClaimed(uint256 indexed projectId, uint256 amount);
    event TokensClaimed(uint256 indexed projectId, address indexed investor, uint256 amount);
    event Refunded(uint256 indexed projectId, address indexed investor, uint256 amount);
    event UnsoldTokensClaimed(uint256 indexed projectId, uint256 amount);
    event PlatformFeeClaimed(uint256 indexed projectId, uint256 amount);
    event ProjectApproved(uint256 projectId);
    event ProjectRejected(uint256 projectId);

    constructor(address _usdtAddress) Ownable(msg.sender) {
        usdtToken = IERC20(_usdtAddress);
    }
    
    /**
     * @dev Create a new project
     * @param _projectId Id of project
     * @param _raiser Address of the project owner
     * @param _tokenAddress Address of the project token
     * @param _tokensToSell Amount of tokens to sell
     * @param _tokenPrice Price per token in USDT (must be easily divisible)
     * @param _endTime Timestamp when the funding period ends
     */
    function createProject(
        uint256 _projectId,
        address _raiser,
        address _tokenAddress,
        uint256 _tokensToSell,
        uint256 _tokenPrice,
        uint256 _endTime
    ) external onlyOwner {
        require(
            _tokenPrice == 10000 || // 0.01 USDT
            _tokenPrice == 50000 || // 0.05 USDT
            _tokenPrice == 100000 || // 0.1 USDT
            _tokenPrice == 500000 || // 0.5 USDT
            _tokenPrice == 1000000, // 1 USDT
            "Invalid token price"
        );
        
        require(_endTime > block.timestamp, "End time must be in the future");
        require(_tokensToSell > 0, "Tokens to sell must be greater than 0");
        require(_raiser != address(0), "Invalid raiser address");
        require(_tokenAddress != address(0), "Invalid token address");
        
        Project storage project = projects[_projectId];
        
        project.id = _projectId;
        project.raiser = _raiser;
        project.tokenAddress = _tokenAddress;
        project.tokensToSell = _tokensToSell;
        project.tokenPrice = _tokenPrice;
        project.endTime = _endTime;
        project.status = ProjectStatus.Created;
        project.platformFeeClaimed = false;
        project.fundsRaised = 0;
        project.claimUnsoldToken = false;
        
        emit ProjectCreated(_projectId, _raiser, _tokensToSell, _tokenPrice, _endTime);
    }
    
    /**
     * @dev Raiser deposits tokens to be sold
     * @param _projectId ID of the project
     */
    function depositTokens(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(msg.sender == project.raiser, "Only raiser can deposit tokens");
        require(project.status != ProjectStatus.Raising, "Tokens already deposited");
        require(block.timestamp < project.endTime, "Project funding period has ended");
        
        IERC20 projectToken = IERC20(project.tokenAddress);
        uint256 tokenAmount = project.tokensToSell;
        
        require(
            projectToken.transferFrom(msg.sender, address(this), tokenAmount),
            "Depositing: Token transfer failed"
        );
        
        project.status = ProjectStatus.Raising;
        
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
        
        require(project.status == ProjectStatus.Raising, "Raiser hasn't deposited tokens yet");
        require(block.timestamp < project.endTime, "Project funding period has ended");
        
        uint256 investmentAmount = _units * USDT_UNIT;
        uint256 tokensToReceive = (investmentAmount / project.tokenPrice);
        
        require(project.tokensSold + tokensToReceive <= project.tokensToSell, "Not enough tokens left");
        
        require(
            usdtToken.transferFrom(msg.sender, address(this), investmentAmount),
            "Investing: USDT transfer failed"
        );
        
        if (project.investments[msg.sender] == 0) {
            project.investorsCount++;
            investorProjects[msg.sender].push(_projectId);
        }
        
        project.investments[msg.sender] += investmentAmount;
        project.fundsRaised += investmentAmount;
        project.tokensSold += tokensToReceive;
        
        emit InvestmentMade(_projectId, msg.sender, investmentAmount);
    }
    
    /**
     * @dev User votes on a project
     * @param _projectId ID of the project
     * @param _approve True to approve, false to reject
     */
    function vote(uint256 _projectId, bool _approve) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(block.timestamp >= project.endTime, "Project funding period has not ended yet");
        require(project.investments[msg.sender] > 0, "Only investors can vote");
        require(!project.hasVoted[msg.sender], "Already voted");
        require(project.status == ProjectStatus.Raising || project.status == ProjectStatus.Voting, "Cannot vote in current state");
        
        if (project.status == ProjectStatus.Raising) {
            project.status = ProjectStatus.Voting;
        }

        project.hasVoted[msg.sender] = true;
        project.voteDecision[msg.sender] = _approve;
        
        if (_approve) {
            project.approvalVotes += project.investments[msg.sender];
        } else {
            project.rejectionVotes += project.investments[msg.sender];
        }

        if (project.votersCount >= (project.investorsCount / 2)){
            if (project.approvalVotes > project.rejectionVotes && 
                project.approvalVotes >= project.fundsRaised / 2) {
                project.status = ProjectStatus.Approved;
                emit ProjectApproved(_projectId);
            } else if (project.rejectionVotes > project.approvalVotes && 
                      project.rejectionVotes > project.fundsRaised / 2) {
                project.status = ProjectStatus.Rejected;
                emit ProjectRejected(_projectId);
            }
        }
        
        project.votersCount++;
        emit VoteCast(_projectId, msg.sender, _approve);
    }
    
    /**
     * @dev Raiser claims funds after successful funding and approval
     * @param _projectId ID of the project
     */
    function claimFunds(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(msg.sender == project.raiser, "Only raiser can claim funds");
        require(block.timestamp >= project.endTime, "Project funding period has not ended yet");
        require(!project.fundsClaimed, "Funds already claimed");
        require(project.status == ProjectStatus.Approved, "Project not approved");
        
        
        uint256 platformFee = (project.fundsRaised * PLATFORM_FEE_PERCENT) / 100;
        uint256 raiserAmount = project.fundsRaised - platformFee;
        
        require(
            usdtToken.transfer(project.raiser, raiserAmount),
            "USDT transfer to raiser failed"
        );
        
        project.fundsClaimed = true;
        project.status = ProjectStatus.Completed;

        emit FundsClaimed(_projectId, raiserAmount);
    }
    
    /**
     * @dev Investor claims tokens after successful funding and approval
     * @param _projectId ID of the project
     */
    function claimTokens(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(block.timestamp >= project.endTime, "Project funding period has not ended yet");
        require(project.status == ProjectStatus.Completed, "Project is not completed");
        require(project.investments[msg.sender] > 0, "No investment found");
        require(!project.hasClaimedTokens[msg.sender], "Tokens already claimed");
        
        uint256 investmentAmount = project.investments[msg.sender];
        uint256 tokensToReceive = (investmentAmount / project.tokenPrice);
        
        project.hasClaimedTokens[msg.sender] = true;
        
        // Transfer tokens to investor
        IERC20 projectToken = IERC20(project.tokenAddress);
        require(
            projectToken.transfer(msg.sender, tokensToReceive),
            "Token transfer failed"
        );
        
        emit TokensClaimed(_projectId, msg.sender, tokensToReceive);
    }
    
    /**
     * @dev Investor gets refund if project is rejected
     * @param _projectId ID of the project
     */
    function getRefund(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(block.timestamp >= project.endTime, "Project funding period has not ended yet");
        require(project.investments[msg.sender] > 0, "No investment found");
        require(project.status == ProjectStatus.Rejected, "Project is not rejected");
        require(!project.refundClaimed[msg.sender], "Already claim refund");
        
        uint256 refundAmount = project.investments[msg.sender];
        project.investments[msg.sender] = 0;
        
        // Transfer USDT back to investor
        require(
            usdtToken.transfer(msg.sender, refundAmount),
            "USDT refund failed"
        );

        project.refundClaimed[msg.sender] = true;
        
        emit Refunded(_projectId, msg.sender, refundAmount);
    }
    
    /**
     * @dev Raiser claims unsold tokens
     * @param _projectId ID of the project
     */
    function claimUnsoldTokens(uint256 _projectId) external nonReentrant {
        Project storage project = projects[_projectId];
        
        require(msg.sender == project.raiser, "Only raiser can claim unsold tokens");
        require(block.timestamp >= project.endTime, "Project funding period has not ended yet");
        require(!project.claimUnsoldToken, "Unsold tokens claimed");
        
        uint256 unsoldTokens = project.tokensToSell - project.tokensSold;
        require(unsoldTokens > 0, "No unsold tokens");
        
        IERC20 projectToken = IERC20(project.tokenAddress);
        require(
            projectToken.transfer(project.raiser, unsoldTokens),
            "Token transfer failed"
        );

        project.claimUnsoldToken = true;
        
        emit UnsoldTokensClaimed(_projectId, unsoldTokens);
    }
    
    /**
     * @dev Platform claims fee
     * @param _projectId ID of the project
     */
    function claimPlatformFee(uint256 _projectId) external onlyOwner nonReentrant {
        Project storage project = projects[_projectId];
        
        require(project.status == ProjectStatus.Completed, "Project is not completed");
        require(!project.platformFeeClaimed, "Platform fee already claimed");
        
        uint256 platformFee = (project.fundsRaised * PLATFORM_FEE_PERCENT) / 100;
        
        // Transfer fee to platform
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
        uint256 endTime,
        uint256 fundsRaised,
        bool fundsClaimed,
        ProjectStatus status,
        uint256 investorsCount,
        uint256 votersCount,
        uint256 approvalPercentage
    ) {
        Project storage project = projects[_projectId];
        
        uint256 _approvalPercentage = 0;
        if (project.fundsRaised > 0) {
            _approvalPercentage = (project.approvalVotes * 100) / project.fundsRaised;
        }
        
        return (
            project.raiser,
            project.tokenAddress,
            project.tokensToSell,
            project.tokensSold,
            project.tokenPrice,
            project.endTime,
            project.fundsRaised,
            project.fundsClaimed,
            project.status,
            project.investorsCount,
            project.votersCount,
            _approvalPercentage
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
        bool voteDecision,
        bool hasClaimedTokens,
        bool hasClaimedRefund
    ) {
        Project storage project = projects[_projectId];
        
        return (
            project.investments[_investor],
            project.hasVoted[_investor],
            project.voteDecision[_investor],
            project.hasClaimedTokens[_investor],
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
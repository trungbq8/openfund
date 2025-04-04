const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("OpenFund Contract", function () {
  // Test variables
  let openFund;
  let usdt;
  let projectToken;
  let owner;
  let raiser;
  let investor1;
  let investor2;
  let investor3;
  let projectId;
  let tokensToSell;
  let tokenPrice;
  let fundingDuration;
  let endFundingTime;

  beforeEach(async function () {
    // Get signers
    [owner, raiser, investor1, investor2, investor3] = await ethers.getSigners();
    
    // Deploy test USDT token
    const TestUSDT = await ethers.getContractFactory("TestUSDT");
    usdt = await TestUSDT.deploy();
    
    // Deploy test project token
    const TestProjectToken = await ethers.getContractFactory("TestProjectToken");
    projectToken = await TestProjectToken.deploy();
    
    // Transfer some project tokens to raiser
    await projectToken.transfer(raiser.address, ethers.parseEther("10000000"));
    
    // Mint USDT to investors
    await usdt.mint(investor1.address, 10000 * 10**6); // 10,000 USDT
    await usdt.mint(investor2.address, 10000 * 10**6); // 10,000 USDT
    await usdt.mint(investor3.address, 10000 * 10**6); // 10,000 USDT
    
    // Deploy OpenFund contract
    const OpenFund = await ethers.getContractFactory("OpenFund");
    openFund = await OpenFund.deploy(usdt.getAddress());
    
    // Set test parameters
    projectId = 1;
    tokensToSell = 1000; // 1,000 tokens for sale
    tokenPrice = 100 * 10**6 / 100; // 1 USDT per token (adjusted for decimals)
    fundingDuration = 7 * 24 * 60 * 60; // 7 days in seconds
    const currentTimestamp = await time.latest();
    endFundingTime = currentTimestamp + fundingDuration;
  });

  describe("Project Creation and Token Deposit", function () {
    it("Should create a project successfully", async function () {
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[0]).to.equal(raiser.address); // raiser
      expect(projectDetails[1]).to.equal(await projectToken.getAddress()); // token address
      expect(projectDetails[2]).to.equal(tokensToSell); // tokensToSell
      expect(projectDetails[4]).to.equal(tokenPrice); // token price
      expect(projectDetails[5]).to.equal(endFundingTime); // endFundingTime
    });
    
    it("Should allow raiser to deposit tokens", async function () {
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      // Approve tokens for deposit
      await projectToken.connect(raiser).approve(
        await openFund.getAddress(),
        ethers.parseEther(tokensToSell.toString())
      );
      
      // Deposit tokens
      await expect(openFund.connect(raiser).depositTokens(projectId))
        .to.emit(openFund, "TokensDeposited")
        .withArgs(projectId, ethers.parseEther(tokensToSell.toString()));
        
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[8]).to.equal(1); // Status should be RaisingPeriod
    });
    
    it("Should not allow non-raiser to deposit tokens", async function () {
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      await expect(openFund.connect(investor1).depositTokens(projectId))
        .to.be.revertedWith("Only raiser can deposit tokens");
    });
  });
  
  describe("Investment Process", function () {
    beforeEach(async function () {
      // Create project and deposit tokens
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      await projectToken.connect(raiser).approve(
        await openFund.getAddress(),
        ethers.parseEther(tokensToSell.toString())
      );
      
      await openFund.connect(raiser).depositTokens(projectId);
    });
    
    it("Should allow investor to invest", async function () {
      const units = 2; // Invest 200 USDT
      
      // Approve USDT for investment
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      
      // Invest
      await expect(openFund.connect(investor1).invest(projectId, units))
        .to.emit(openFund, "InvestmentMade");
        
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(units * 100 * 10**6); // fundsRaised
      
      const investmentDetails = await openFund.getInvestmentDetails(projectId, investor1.address);
      expect(investmentDetails[0]).to.equal(units * 100 * 10**6); // investment amount
    });
    
    it("Should not allow investment exceeding maximum per user", async function () {
      const units = 11; // More than MAX_INVESTMENT_UNITS (10)
      
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      
      await expect(openFund.connect(investor1).invest(projectId, units))
        .to.be.revertedWith("Invalid units amount");
    });
    
    it("Should not allow investment after funding period", async function () {
      const units = 2;
      
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      
      // Advance time to after funding period
      await time.increaseTo(endFundingTime + 1);
      
      await expect(openFund.connect(investor1).invest(projectId, units))
        .to.be.revertedWith("Project funding period has ended");
    });
  });
  
  describe("Voting and Claiming Process", function () {
    beforeEach(async function () {
      // Create project and deposit tokens
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      await projectToken.connect(raiser).approve(
        await openFund.getAddress(),
        ethers.parseEther(tokensToSell.toString())
      );
      
      await openFund.connect(raiser).depositTokens(projectId);
      
      // Investors invest
      const units = 2; // 200 USDT each
      
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor1).invest(projectId, units);
      
      await usdt.connect(investor2).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor2).invest(projectId, units);
    });
    
    it("Should allow voting during voting period", async function () {
      // Advance time to voting period
      await time.increaseTo(endFundingTime + 1);
      
      await expect(openFund.connect(investor1).voteForRefund(projectId))
        .to.emit(openFund, "VoteCast")
        .withArgs(projectId, investor1.address);
        
      const investmentDetails = await openFund.getInvestmentDetails(projectId, investor1.address);
      expect(investmentDetails[1]).to.be.true; // hasVoted
    });
    
    it("Should trigger refund if vote threshold is reached", async function () {
      // Advance time to voting period
      await time.increaseTo(endFundingTime + 1);
      
      // Both investors vote for refund (which should be over 50%)
      await openFund.connect(investor1).voteForRefund(projectId);
      await openFund.connect(investor2).voteForRefund(projectId);
      
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[8]).to.equal(3); // Status should be FundingFailed
    });
    
    it("Should allow raiser to claim funds after voting period with no refund vote majority", async function () {
      // Advance time to after voting period
      await time.increaseTo(endFundingTime + 3 * 24 * 60 * 60 + 1);
      
      await expect(openFund.connect(raiser).claimFunds(projectId))
        .to.emit(openFund, "FundsClaimed");
        
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[8]).to.equal(4); // Status should be FundingCompleted
    });
    
    it("Should allow platform to claim fee after funds are claimed", async function () {
      // Advance time to after voting period
      await time.increaseTo(endFundingTime + 3 * 24 * 60 * 60 + 1);
      
      await openFund.connect(raiser).claimFunds(projectId);
      
      await expect(openFund.connect(owner).claimPlatformFee(projectId))
        .to.emit(openFund, "PlatformFeeClaimed");
    });
  });
  
  describe("Refund Process", function () {
    beforeEach(async function () {
      // Create project and deposit tokens
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      await projectToken.connect(raiser).approve(
        await openFund.getAddress(),
        ethers.parseEther(tokensToSell.toString())
      );
      
      await openFund.connect(raiser).depositTokens(projectId);
      
      // Investors invest
      const units = 2; // 200 USDT each
      
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor1).invest(projectId, units);
      
      await usdt.connect(investor2).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor2).invest(projectId, units);
      
      // Advance time to voting period and vote for refund
      await time.increaseTo(endFundingTime + 1);
      await openFund.connect(investor1).voteForRefund(projectId);
      await openFund.connect(investor2).voteForRefund(projectId);
    });
    
    it("Should allow investors to get refund if project fails", async function () {
      // Approve tokens to be transferred back for refund
      const tokensReceived = ethers.parseEther("200"); // 200 tokens (200 USDT at 1 USDT per token)
      await projectToken.connect(investor1).approve(
        await openFund.getAddress(),
        tokensReceived
      );
      
      await expect(openFund.connect(investor1).getRefund(projectId))
        .to.emit(openFund, "Refunded");
        
      const investmentDetails = await openFund.getInvestmentDetails(projectId, investor1.address);
      expect(investmentDetails[3]).to.be.true; // hasClaimedRefund
    });
    
    it("Should allow raiser to claim unsold tokens", async function () {
      await expect(openFund.connect(raiser).claimUnsoldTokens(projectId))
        .to.emit(openFund, "UnsoldTokensClaimed");
    });
  });
  
  describe("Edge Cases", function () {
    beforeEach(async function () {
      // Create project and deposit tokens
      await openFund.createProject(
        projectId,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      await projectToken.connect(raiser).approve(
        await openFund.getAddress(),
        ethers.parseEther(tokensToSell.toString())
      );
      
      await openFund.connect(raiser).depositTokens(projectId);
    });
    
    it("Should not allow double claiming of funds", async function () {
      // Invest some funds
      const units = 2;
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor1).invest(projectId, units);
      
      // Advance time to after voting period
      await time.increaseTo(endFundingTime + 3 * 24 * 60 * 60 + 1);
      
      // First claim works
      await openFund.connect(raiser).claimFunds(projectId);
      
      // Second claim should fail
      await expect(openFund.connect(raiser).claimFunds(projectId))
        .to.be.revertedWith("Funds already claimed");
    });
    
    it("Should not allow refund if project is not rejected", async function () {
      // Invest some funds
      const units = 2;
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor1).invest(projectId, units);
      
      // Advance time to after funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Try to claim refund without project being rejected
      await expect(openFund.connect(investor1).getRefund(projectId))
        .to.be.revertedWith("Project is not rejected");
    });
    
    it("Should track investor projects correctly", async function () {
      // Invest in project
      const units = 2;
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor1).invest(projectId, units);
      
      // Create second project
      const projectId2 = 2;
      await openFund.createProject(
        projectId2,
        raiser.address,
        await projectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        await projectToken.decimals()
      );
      
      await projectToken.connect(raiser).approve(
        await openFund.getAddress(),
        ethers.parseEther(tokensToSell.toString())
      );
      
      await openFund.connect(raiser).depositTokens(projectId2);
      
      // Invest in second project
      await usdt.connect(investor1).approve(
        await openFund.getAddress(),
        units * 100 * 10**6
      );
      await openFund.connect(investor1).invest(projectId2, units);
      
      // Check investor projects
      const investorProjects = await openFund.getInvestorProjects(investor1.address);
      expect(investorProjects.length).to.equal(2);
      expect(investorProjects[0]).to.equal(projectId);
      expect(investorProjects[1]).to.equal(projectId2);
    });
  });
});
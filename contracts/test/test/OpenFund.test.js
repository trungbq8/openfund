const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("OpenFund", function () {
  let openFund;
  let testUSDT;
  let testProjectToken;
  let owner;
  let projectRaiser;
  let investor1;
  let investor2;
  let investor3;
  let projectId;
  let tokenPrice;
  let tokensToSell;
  let decimal;
  let endFundingTime;

  beforeEach(async function () {
    // Deploy test tokens and contracts
    [owner, projectRaiser, investor1, investor2, investor3] = await ethers.getSigners();
    
    // Deploy TestUSDT
    const TestUSDT = await ethers.getContractFactory("TestUSDT");
    testUSDT = await TestUSDT.deploy();
    
    // Deploy TestProjectToken
    const TestProjectToken = await ethers.getContractFactory("TestProjectToken");
    testProjectToken = await TestProjectToken.deploy();
    
    // Deploy OpenFund
    const OpenFund = await ethers.getContractFactory("OpenFund");
    openFund = await OpenFund.deploy(await testUSDT.getAddress());
    
    // Project parameters
    projectId = 1;
    tokenPrice = 500000; // 0.5 USDT (decimal 6)
    tokensToSell = 100000; // 100,000 tokens
    decimal = 18;
    
    // Set funding end time to 7 days from now
    const currentTimestamp = await time.latest();
    endFundingTime = currentTimestamp + time.duration.days(7);
    
    // Mint USDT to investors
    await testUSDT.mint(investor1.address, ethers.parseUnits("10000", 6));
    await testUSDT.mint(investor2.address, ethers.parseUnits("10000", 6));
    await testUSDT.mint(investor3.address, ethers.parseUnits("10000", 6));
    
    // Transfer project tokens to raiser
    await testProjectToken.transfer(projectRaiser.address, ethers.parseUnits("500000", 18));
  });

  describe("Project Creation and Setup", function () {
    it("Should create a project successfully", async function () {
      await expect(
        openFund.createProject(
          projectId,
          projectRaiser.address,
          await testProjectToken.getAddress(),
          tokensToSell,
          tokenPrice,
          endFundingTime,
          decimal
        )
      ).to.emit(openFund, "ProjectCreated")
        .withArgs(projectId, projectRaiser.address, tokensToSell, tokenPrice, endFundingTime);
      
      // Verify project details
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails.raiser).to.equal(projectRaiser.address);
      expect(projectDetails.tokenAddress).to.equal(await testProjectToken.getAddress());
      expect(projectDetails.tokensToSell).to.equal(tokensToSell);
      expect(projectDetails.tokenPrice).to.equal(tokenPrice);
    });

    it("Should allow raiser to deposit tokens", async function () {
      // Create project
      await openFund.createProject(
        projectId,
        projectRaiser.address,
        await testProjectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        decimal
      );
      
      // Approve tokens
      await testProjectToken.connect(projectRaiser).approve(
        await openFund.getAddress(),
        ethers.parseUnits(tokensToSell.toString(), decimal)
      );
      
      // Deposit tokens
      await expect(
        openFund.connect(projectRaiser).depositTokens(projectId)
      ).to.emit(openFund, "TokensDeposited")
        .withArgs(projectId, ethers.parseUnits(tokensToSell.toString(), decimal));
      
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails.status).to.equal(1); // RaisingPeriod
    });
  });

  describe("Investment Process", function () {
    beforeEach(async function () {
      // Create project
      await openFund.createProject(
        projectId,
        projectRaiser.address,
        await testProjectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        decimal
      );
      
      // Approve and deposit tokens
      await testProjectToken.connect(projectRaiser).approve(
        await openFund.getAddress(),
        ethers.parseUnits(tokensToSell.toString(), decimal)
      );
      await openFund.connect(projectRaiser).depositTokens(projectId);
      
      // Approve USDT for investment
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("1000", 6)
      );
      await testUSDT.connect(investor2).approve(
        await openFund.getAddress(),
        ethers.parseUnits("1000", 6)
      );
    });

    it("Should allow investors to invest", async function () {
      // Invest 1 unit (100 USDT)
      await expect(
        openFund.connect(investor1).invest(projectId, 1)
      ).to.emit(openFund, "InvestmentMade");
      
      // Check investment details
      const investmentDetails = await openFund.getInvestmentDetails(projectId, investor1.address);
      expect(investmentDetails.investmentAmount).to.equal(ethers.parseUnits("100", 6));
      
      // Check project details after investment
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails.fundsRaised).to.equal(ethers.parseUnits("100", 6));
      expect(projectDetails.investorsCount).to.equal(1);
      
      // Check token balance of investor
      const expectedTokens = ethers.parseUnits("100", 6) / BigInt(projectDetails.tokenPrice);
      const tokenBalance = await testProjectToken.balanceOf(investor1.address);
      expect(tokenBalance).to.equal(ethers.parseUnits(expectedTokens.toString(), decimal));
    });

    it("Should not allow investment exceeding maximum units", async function () {
      // Try to invest 11 units (exceeds max 10)
      await expect(
        openFund.connect(investor1).invest(projectId, 11)
      ).to.be.revertedWith("Invalid units amount");
    });

    it("Should not allow cumulative investment exceeding maximum units", async function () {
      // Invest 5 units first
      await openFund.connect(investor1).invest(projectId, 5);
      
      // Try to invest 6 more units (total would be 11, exceeding max 10)
      await expect(
        openFund.connect(investor1).invest(projectId, 6)
      ).to.be.revertedWith("Exceed maximum investment per project");

      // Should allow up to max
      await openFund.connect(investor1).invest(projectId, 5);
    });
  });

  describe("Voting and Fund Release", function () {
    beforeEach(async function () {
      // Create project
      await openFund.createProject(
        projectId,
        projectRaiser.address,
        await testProjectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        decimal
      );
      
      // Approve and deposit tokens
      await testProjectToken.connect(projectRaiser).approve(
        await openFund.getAddress(),
        ethers.parseUnits(tokensToSell.toString(), decimal)
      );
      await openFund.connect(projectRaiser).depositTokens(projectId);
      
      // Approve USDT for investments
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("1000", 6)
      );
      await testUSDT.connect(investor2).approve(
        await openFund.getAddress(),
        ethers.parseUnits("1000", 6)
      );
      await testUSDT.connect(investor3).approve(
        await openFund.getAddress(),
        ethers.parseUnits("1000", 6)
      );
      
      // Make investments
      await openFund.connect(investor1).invest(projectId, 2); // 200 USDT
      await openFund.connect(investor2).invest(projectId, 3); // 300 USDT
      await openFund.connect(investor3).invest(projectId, 1); // 100 USDT
    });

    it("Should not allow voting before funding period ends", async function () {
      await expect(
        openFund.connect(investor1).voteForRefund(projectId)
      ).to.be.revertedWith("Not in voting period");
    });

    it("Should allow voting after funding period ends", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Vote for refund
      await expect(
        openFund.connect(investor1).voteForRefund(projectId)
      ).to.emit(openFund, "VoteCast")
        .withArgs(projectId, investor1.address);
      
      // Check voting status
      const investmentDetails = await openFund.getInvestmentDetails(projectId, investor1.address);
      expect(investmentDetails.hasVoted).to.be.true;

      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails.status).to.equal(2); // VotingPeriod
      expect(projectDetails.votersForRefundCount).to.equal(1);
    });

    it("Should fail project if majority votes for refund", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // All investors vote for refund (more than 50%)
      await openFund.connect(investor1).voteForRefund(projectId);
      await openFund.connect(investor2).voteForRefund(projectId);
      await openFund.connect(investor3).voteForRefund(projectId);
      
      // Check project status
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails.status).to.equal(3); // FundingFailed
    });

    it("Should allow refunds when project fails", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // All investors vote for refund
      await openFund.connect(investor1).voteForRefund(projectId);
      await openFund.connect(investor2).voteForRefund(projectId); 
      await openFund.connect(investor3).voteForRefund(projectId);
      
      // Fast forward to refund period - must be AFTER voting period but BEFORE refund period ends
      // Based on contract: endVotingTime = endFundingTime + 3 days; endRefundTime = endFundingTime + 4 days
      await time.increaseTo(endFundingTime + time.duration.days(3) + 1); // Just after voting period ends
      
      // Get USDT balance before refund
      const usdtBalanceBefore = await testUSDT.balanceOf(investor1.address);
      
      // Approve tokens to be returned
      const tokenBalance = await testProjectToken.balanceOf(investor1.address);
      await testProjectToken.connect(investor1).approve(
        await openFund.getAddress(),
        tokenBalance
      );
      
      // Get refund
      await expect(
        openFund.connect(investor1).getRefund(projectId)
      ).to.emit(openFund, "Refunded");
      
      // Check USDT balance after refund
      const usdtBalanceAfter = await testUSDT.balanceOf(investor1.address);
      expect(usdtBalanceAfter - usdtBalanceBefore).to.equal(ethers.parseUnits("200", 6));
      
      // Check refund claimed status
      const investmentDetails = await openFund.getInvestmentDetails(projectId, investor1.address);
      expect(investmentDetails.hasClaimedRefund).to.be.true;
    });

    it("Should allow raiser to claim funds after successful funding", async function () {
      // Fast forward time beyond refund period
      await time.increaseTo(endFundingTime + time.duration.days(4) + 1);
      
      // Get USDT balance before claim
      const usdtBalanceBefore = await testUSDT.balanceOf(projectRaiser.address);
      
      // Raiser claims funds
      await expect(
        openFund.connect(projectRaiser).claimFunds(projectId)
      ).to.emit(openFund, "FundsClaimed");
      
      // Check USDT balance after claim
      const usdtBalanceAfter = await testUSDT.balanceOf(projectRaiser.address);
      
      // Total investment is 600 USDT, platform fee is 5%, so raiser gets 570 USDT
      const expectedFunds = ethers.parseUnits("600", 6) * BigInt(95) / BigInt(100);
      expect(usdtBalanceAfter - usdtBalanceBefore).to.equal(expectedFunds);
      
      // Check project status
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails.status).to.equal(4); // FundingCompleted
    });

    it("Should allow platform to claim fee after successful funding", async function () {
      // Fast forward time beyond refund period
      await time.increaseTo(endFundingTime + time.duration.days(4) + 1);
      
      // Raiser claims funds first
      await openFund.connect(projectRaiser).claimFunds(projectId);
      
      // Get USDT balance before claim
      const usdtBalanceBefore = await testUSDT.balanceOf(owner.address);
      
      // Platform claims fee
      await expect(
        openFund.connect(owner).claimPlatformFee(projectId)
      ).to.emit(openFund, "PlatformFeeClaimed");
      
      // Check USDT balance after claim
      const usdtBalanceAfter = await testUSDT.balanceOf(owner.address);
      
      // Total investment is 600 USDT, platform fee is 5%, so platform gets 30 USDT
      const expectedFee = ethers.parseUnits("600", 6) * BigInt(5) / BigInt(100);
      expect(usdtBalanceAfter - usdtBalanceBefore).to.equal(expectedFee);
    });
  });

  describe("Unsold Tokens", function () {
    beforeEach(async function () {
      // Create project
      await openFund.createProject(
        projectId,
        projectRaiser.address,
        await testProjectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        decimal
      );
      
      // Approve and deposit tokens
      await testProjectToken.connect(projectRaiser).approve(
        await openFund.getAddress(),
        ethers.parseUnits(tokensToSell.toString(), decimal)
      );
      await openFund.connect(projectRaiser).depositTokens(projectId);
      
      // Approve USDT for investment
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("1000", 6)
      );
      
      // Invest in part of the tokens
      await openFund.connect(investor1).invest(projectId, 2); // 200 USDT
    });

    it("Should allow raiser to claim unsold tokens", async function () {
      // Fast forward time beyond refund period
      await time.increaseTo(endFundingTime + time.duration.days(4) + 1);
      
      // Get token balance before claim
      const tokenBalanceBefore = await testProjectToken.balanceOf(projectRaiser.address);
      
      // Claim unsold tokens
      await expect(
        openFund.connect(projectRaiser).claimUnsoldTokens(projectId)
      ).to.emit(openFund, "UnsoldTokensClaimed");
      
      // Check token balance after claim
      const tokenBalanceAfter = await testProjectToken.balanceOf(projectRaiser.address);
      
      // Calculate expected unsold tokens (using BigInt consistently)
      const tokensPerUnit = BigInt(ethers.parseUnits("100", 6)) / BigInt(tokenPrice);
      const tokensSold = tokensPerUnit * 2n;
      const unsoldTokens = BigInt(tokensToSell) - tokensSold;
      const expectedTokens = ethers.parseUnits(unsoldTokens.toString(), decimal);
      
      // Compare with precision loss due to integer division
      const difference = tokenBalanceAfter - tokenBalanceBefore;
      expect(difference).to.be.closeTo(expectedTokens, ethers.parseUnits("1", decimal));
    });
  });

  describe("Edge Cases", function () {
    beforeEach(async function () {
      // Create project
      await openFund.createProject(
        projectId,
        projectRaiser.address,
        await testProjectToken.getAddress(),
        tokensToSell,
        tokenPrice,
        endFundingTime,
        decimal
      );
      
      // Approve and deposit tokens
      await testProjectToken.connect(projectRaiser).approve(
        await openFund.getAddress(),
        ethers.parseUnits(tokensToSell.toString(), decimal)
      );
      await openFund.connect(projectRaiser).depositTokens(projectId);
    });

    it("Should not allow non-investor to vote", async function () {
      // Fast forward time to voting period
      await time.increaseTo(endFundingTime + 1);
      
      // Try to vote without having invested
      await expect(
        openFund.connect(investor3).voteForRefund(projectId)
      ).to.be.revertedWith("Only token holders can vote");
    });

    it("Should not allow multiple votes from the same investor", async function () {
      // Invest first
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("100", 6)
      );
      await openFund.connect(investor1).invest(projectId, 1);
      
      // Fast forward time to voting period
      await time.increaseTo(endFundingTime + 1);
      
      // Vote once
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // Try to vote again
      await expect(
        openFund.connect(investor1).voteForRefund(projectId)
      ).to.be.revertedWith("Already voted");
    });

    it("Should not allow refunds before voting period ends", async function () {
      // Invest first
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("100", 6)
      );
      await openFund.connect(investor1).invest(projectId, 1);
      
      // Fast forward time to voting period
      await time.increaseTo(endFundingTime + 1);
      
      // Vote for refund
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // Try to get refund before voting period ends
      await expect(
        openFund.connect(investor1).getRefund(projectId)
      ).to.be.revertedWith("Not in refund period");
    });
  });
});
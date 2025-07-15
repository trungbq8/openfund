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
      expect(projectDetails[0]).to.equal(projectRaiser.address); // raiser
      expect(projectDetails[1]).to.equal(await testProjectToken.getAddress()); // tokenAddress
      expect(projectDetails[2]).to.equal(tokensToSell); // tokensToSell
      expect(projectDetails[4]).to.equal(tokenPrice); // tokenPrice
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
      expect(projectDetails[7]).to.equal(1); // RaisingPeriod
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
      expect(investmentDetails[0]).to.equal(ethers.parseUnits("100", 6)); // investmentAmount
      
      // Check project details after investment
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[6]).to.equal(ethers.parseUnits("100", 6)); // fundsRaised
      
      // Check token balance of investor
      const expectedTokens = ethers.parseUnits("100", 6) / BigInt(projectDetails[4]); // tokenPrice
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
      expect(investmentDetails[1]).to.be.true; // hasVoted

      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(2); // VotingPeriod status
    });

    it("Should allow investors to vote only once", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Vote for refund
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // Try to vote again
      await expect(
        openFund.connect(investor1).voteForRefund(projectId)
      ).to.be.revertedWith("Already voted");
    });

    it("Should update vote amount correctly when user votes", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Vote for refund
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // Check voting status and vote amount
      const projectDetails = await openFund.getProjectDetails(projectId);
      
      // Calculate expected token amount that investor1 has (2 units = 200 USDT)
      const tokensForTwoUnits = ethers.parseUnits("200", 6) / BigInt(tokenPrice);
      expect(projectDetails[9]).to.equal(tokensForTwoUnits); // voteForRefundAmount
      
      // Vote with another investor
      await openFund.connect(investor2).voteForRefund(projectId);
      
      // Check updated vote amount
      const updatedDetails = await openFund.getProjectDetails(projectId);
      
      // Calculate expected token amount that investor2 has (3 units = 300 USDT)
      const tokensForThreeUnits = ethers.parseUnits("300", 6) / BigInt(tokenPrice);
      expect(updatedDetails[9]).to.equal(tokensForTwoUnits + tokensForThreeUnits); // voteForRefundAmount
    });

    it("Should emit ProjectFailed event when majority votes for refund", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Investor1 and Investor2 vote for refund (more than 50% of tokens)
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // The second vote should trigger project failure
      await expect(
        openFund.connect(investor2).voteForRefund(projectId)
      ).to.emit(openFund, "ProjectFailed")
        .withArgs(projectId);
      
      // Check project status
      const projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(3); // FundingFailed
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
      expect(investmentDetails[2]).to.be.true; // hasClaimedRefund
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
      expect(projectDetails[7]).to.equal(4); // FundingCompleted
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

    it("Should not allow claiming unsold tokens before refund period ends", async function () {
      // Invest first
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("100", 6)
      );
      await openFund.connect(investor1).invest(projectId, 1);
      
      // Try to claim unsold tokens before refund period ends
      await expect(
        openFund.connect(projectRaiser).claimUnsoldTokens(projectId)
      ).to.be.revertedWith("It is not time to claim unsold tokens");
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

    it("Should not allow claiming platform fee when project has failed", async function () {
      // Invest first
      await testUSDT.connect(investor1).approve(
        await openFund.getAddress(),
        ethers.parseUnits("100", 6)
      );
      await openFund.connect(investor1).invest(projectId, 1);
      
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Vote for refund to make project fail
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // Fast forward time beyond refund period
      await time.increaseTo(endFundingTime + time.duration.days(4) + 1);
      
      // Try to claim platform fee when project has failed
      await expect(
        openFund.connect(owner).claimPlatformFee(projectId)
      ).to.be.revertedWith("Project funding is failed");
    });
  });
  
  describe("Project Status and State Transitions", function () {
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

    it("Should transition from RaisingPeriod to VotingPeriod when first vote is cast", async function () {
      // Verify project is in RaisingPeriod
      let projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(1); // RaisingPeriod
      
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Cast first vote
      await openFund.connect(investor1).voteForRefund(projectId);
      
      // Verify project is now in VotingPeriod
      projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(2); // VotingPeriod
    });
    
    it("Should not transition to FundingFailed unless vote threshold is reached", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // Cast vote from smallest investor (not enough for majority)
      await openFund.connect(investor3).voteForRefund(projectId);
      
      // Verify project is still in VotingPeriod
      let projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(2); // VotingPeriod
      
      // Cast vote from another investor to reach threshold
      await openFund.connect(investor2).voteForRefund(projectId);
      
      // Verify project is now in FundingFailed
      projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(3); // FundingFailed
    });
    
    it("Should allow raiser to claim funds even when project failed after refund period", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // All investors vote for refund
      await openFund.connect(investor1).voteForRefund(projectId);
      await openFund.connect(investor2).voteForRefund(projectId);
      await openFund.connect(investor3).voteForRefund(projectId);
      
      // Verify project failed
      let projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(3); // FundingFailed
      
      // Some investors claim refunds
      await time.increaseTo(endFundingTime + time.duration.days(3) + 1); // Just after voting period
      
      // Approve tokens to be returned
      const investor1TokenBalance = await testProjectToken.balanceOf(investor1.address);
      await testProjectToken.connect(investor1).approve(
        await openFund.getAddress(),
        investor1TokenBalance
      );
      
      // Get refund for investor1 only
      await openFund.connect(investor1).getRefund(projectId);
      
      // Fast forward to after refund period
      await time.increaseTo(endFundingTime + time.duration.days(4) + 1);
      
      // Get USDT balance before claim
      const usdtBalanceBefore = await testUSDT.balanceOf(projectRaiser.address);
      
      // Raiser claims remaining funds
      await expect(
        openFund.connect(projectRaiser).claimFunds(projectId)
      ).to.emit(openFund, "FundsClaimed");
      
      // Check USDT balance after claim
      const usdtBalanceAfter = await testUSDT.balanceOf(projectRaiser.address);
      
      // Only investor1 got refund (200 USDT), so 400 USDT remains for raiser
      const expectedFunds = ethers.parseUnits("400", 6);
      expect(usdtBalanceAfter - usdtBalanceBefore).to.equal(expectedFunds);
      
      // Verify project status remains as FundingFailed
      projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[7]).to.equal(3); // Still FundingFailed
    });
    
    it("Should correctly track tokensSold during refund process", async function () {
      // Fast forward time to end of funding period
      await time.increaseTo(endFundingTime + 1);
      
      // All investors vote for refund
      await openFund.connect(investor1).voteForRefund(projectId);
      await openFund.connect(investor2).voteForRefund(projectId);
      await openFund.connect(investor3).voteForRefund(projectId);
      
      // Fast forward to refund period
      await time.increaseTo(endFundingTime + time.duration.days(3) + 1);
      
      // Check initial tokensSold
      let projectDetails = await openFund.getProjectDetails(projectId);
      const initialTokensSold = projectDetails[3]; // tokensSold
      
      // Calculate expected tokens for investor1 (2 units = 200 USDT)
      const tokensForTwoUnits = ethers.parseUnits("200", 6) / BigInt(tokenPrice);
      
      // Approve tokens to be returned
      const investor1TokenBalance = await testProjectToken.balanceOf(investor1.address);
      await testProjectToken.connect(investor1).approve(
        await openFund.getAddress(),
        investor1TokenBalance
      );
      
      // Get refund for investor1
      await openFund.connect(investor1).getRefund(projectId);
      
      // Check updated tokensSold
      projectDetails = await openFund.getProjectDetails(projectId);
      expect(projectDetails[3]).to.equal(initialTokensSold - tokensForTwoUnits); // tokensSold
    });
  });
});
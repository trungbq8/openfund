const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with the account:", deployer.address);

  // Deploy TestUSDT
  const TestUSDT = await ethers.getContractFactory("TestUSDT");
  const testUSDT = await TestUSDT.deploy();
  await testUSDT.waitForDeployment();
  console.log("TestUSDT deployed to:", await testUSDT.getAddress());

  // Deploy OpenFund
  const OpenFund = await ethers.getContractFactory("OpenFund");
  const openFund = await OpenFund.deploy(await testUSDT.getAddress());
  await openFund.waitForDeployment();
  console.log("OpenFund deployed to:", await openFund.getAddress());

  // Deploy TestProjectToken
  const TestProjectToken = await ethers.getContractFactory("TestProjectToken");
  const projectToken = await TestProjectToken.deploy();
  await projectToken.waitForDeployment();
  console.log("TestProjectToken deployed to:", await projectToken.getAddress());
}

main();

describe("OpenFund", function () {
  let openFund;
  let testUSDT;
  let projectToken;
  let owner;
  let raiser;
  let investor1;
  let investor2;
  let investor3;
  
  const PROJECT_ID = 1;
  const TOKEN_PRICE = 100000; // 0.1 USDT
  const TOKENS_TO_SELL = ethers.parseEther("1000000"); // 1 million tokens
  const PLATFORM_FEE_PERCENT = 5;
  const USDT_UNIT = ethers.parseUnits("100", 6); // 100 USDT
  const MAX_INVESTMENT_UNITS = 10;

  beforeEach(async function () {
    // Get signers
    [owner, raiser, investor1, investor2, investor3] = await ethers.getSigners();
    
    // Deploy TestUSDT
    const TestUSDT = await ethers.getContractFactory("TestUSDT");
    testUSDT = await TestUSDT.deploy();
    
    // Deploy TestProjectToken
    const TestProjectToken = await ethers.getContractFactory("TestProjectToken");
    projectToken = await TestProjectToken.deploy();
    
    // Deploy OpenFund
    const OpenFund = await ethers.getContractFactory("OpenFund");
    openFund = await OpenFund.deploy(await testUSDT.getAddress());
    
    // Distribute USDT to investors
    await testUSDT.mint(investor1.address, ethers.parseUnits("1000", 6)); // 1000 USDT
    await testUSDT.mint(investor2.address, ethers.parseUnits("2000", 6)); // 2000 USDT
    await testUSDT.mint(investor3.address, ethers.parseUnits("3000", 6)); // 3000 USDT
    
    // Transfer project tokens to raiser
    await projectToken.transfer(raiser.address, TOKENS_TO_SELL);
    
    // Set approval for contract to spend tokens
    await testUSDT.connect(investor1).approve(await openFund.getAddress(), ethers.parseUnits("1000", 6));
    await testUSDT.connect(investor2).approve(await openFund.getAddress(), ethers.parseUnits("2000", 6));
    await testUSDT.connect(investor3).approve(await openFund.getAddress(), ethers.parseUnits("3000", 6));
    await projectToken.connect(raiser).approve(await openFund.getAddress(), TOKENS_TO_SELL);
    
    // Current timestamp
    const currentTime = await time.latest();
    
    // Create project
    await openFund.createProject(
      PROJECT_ID,
      raiser.address,
      await projectToken.getAddress(),
      TOKENS_TO_SELL,
      TOKEN_PRICE,
      currentTime + 86400 // End time is 1 day from now
    );
  });
  
  describe("Project Creation", function () {
    it("Should create a project with correct parameters", async function () {
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      
      expect(projectDetails.raiser).to.equal(raiser.address);
      expect(projectDetails.tokenAddress).to.equal(await projectToken.getAddress());
      expect(projectDetails.tokensToSell).to.equal(TOKENS_TO_SELL);
      expect(projectDetails.tokenPrice).to.equal(TOKEN_PRICE);
      expect(projectDetails.status).to.equal(0); // ProjectStatus.Created
    });
    
    it("Should not allow non-owner to create a project", async function () {
      const currentTime = await time.latest();
      
      await expect(
        openFund.connect(raiser).createProject(
          2,
          raiser.address,
          await projectToken.getAddress(),
          TOKENS_TO_SELL,
          TOKEN_PRICE,
          currentTime + 86400
        )
      ).to.be.revertedWithCustomError(openFund, "OwnableUnauthorizedAccount");
    });
    
    it("Should not allow invalid token price", async function () {
      const currentTime = await time.latest();
      
      await expect(
        openFund.createProject(
          2,
          raiser.address,
          await projectToken.getAddress(),
          TOKENS_TO_SELL,
          123456, // Invalid price
          currentTime + 86400
        )
      ).to.be.revertedWith("Invalid token price");
    });
  });
  
  describe("Token Deposit", function () {
    it("Should allow raiser to deposit tokens", async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.status).to.equal(1); // ProjectStatus.Raising
      
      // Check contract balance
      expect(await projectToken.balanceOf(await openFund.getAddress())).to.equal(TOKENS_TO_SELL);
    });
    
    it("Should not allow non-raiser to deposit tokens", async function () {
      await expect(
        openFund.connect(investor1).depositTokens(PROJECT_ID)
      ).to.be.revertedWith("Only raiser can deposit tokens");
    });
  });
  
  describe("Investment", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
    });
    
    it("Should allow investors to invest", async function () {
      const investmentUnits = 2; // 200 USDT
      await openFund.connect(investor1).invest(PROJECT_ID, investmentUnits);
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.fundsRaised).to.equal(investmentUnits * USDT_UNIT);
      
      const investmentDetails = await openFund.getInvestmentDetails(PROJECT_ID, investor1.address);
      expect(investmentDetails.investmentAmount).to.equal(investmentUnits * USDT_UNIT);
    });
    
    it("Should update tokensSold correctly", async function () {
      const investmentUnits = 3; // 300 USDT
      await openFund.connect(investor1).invest(PROJECT_ID, investmentUnits);
      
      const investmentAmount = investmentUnits * USDT_UNIT;
      const expectedTokens = investmentAmount / TOKEN_PRICE;
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.tokensSold).to.equal(expectedTokens);
    });
    
    it("Should not allow investment with too many units", async function () {
      await expect(
        openFund.connect(investor1).invest(PROJECT_ID, MAX_INVESTMENT_UNITS + 1)
      ).to.be.revertedWith("Invalid units amount");
    });

    it("Should record project in investor's portfolio", async function() {
      await openFund.connect(investor1).invest(PROJECT_ID, 1);
      const investorProjects = await openFund.getInvestorProjects(investor1.address);
      expect(investorProjects.length).to.equal(1);
      expect(investorProjects[0]).to.equal(PROJECT_ID);
    });
  });
  
  describe("Voting", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      await openFund.connect(investor1).invest(PROJECT_ID, 2); // 200 USDT
      await openFund.connect(investor2).invest(PROJECT_ID, 3); // 300 USDT
      await openFund.connect(investor3).invest(PROJECT_ID, 5); // 500 USDT
      
      // Fast forward to end of funding period
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      await time.increaseTo(projectDetails.endTime);
    });
    
    it("Should allow investors to vote", async function () {
      await openFund.connect(investor1).vote(PROJECT_ID, true); // Approve
      
      const investmentDetails = await openFund.getInvestmentDetails(PROJECT_ID, investor1.address);
      expect(investmentDetails.hasVoted).to.be.true;
      expect(investmentDetails.voteDecision).to.be.true;
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.status).to.equal(2); // ProjectStatus.Voting
    });
    
    it("Should not allow non-investors to vote", async function () {
      await expect(
        openFund.connect(owner).vote(PROJECT_ID, true)
      ).to.be.revertedWith("Only investors can vote");
    });
    
    it("Should not allow double voting", async function () {
      await openFund.connect(investor1).vote(PROJECT_ID, true);
      
      await expect(
        openFund.connect(investor1).vote(PROJECT_ID, false)
      ).to.be.revertedWith("Already voted");
    });
    
    it("Should approve project with majority approval", async function () {
      // Total funds raised: 1000 USDT
      // Need > 50% to approve, or > 500 USDT in approval votes
      
      await openFund.connect(investor3).vote(PROJECT_ID, true); // 500 USDT approve
      await openFund.connect(investor1).vote(PROJECT_ID, true); // 200 USDT approve
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.status).to.equal(3); // ProjectStatus.Approved
    });
    
    it("Should reject project with majority rejection", async function () {
      // Total funds raised: 1000 USDT
      // Need > 50% to reject, or > 500 USDT in rejection votes
      
      await openFund.connect(investor3).vote(PROJECT_ID, false); // 500 USDT reject
      await openFund.connect(investor1).vote(PROJECT_ID, false); // 200 USDT reject
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.status).to.equal(4); // ProjectStatus.Rejected
    });
  });
  
  describe("Funds Claiming", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      await openFund.connect(investor1).invest(PROJECT_ID, 2); // 200 USDT
      await openFund.connect(investor2).invest(PROJECT_ID, 3); // 300 USDT
      await openFund.connect(investor3).invest(PROJECT_ID, 5); // 500 USDT
      
      // Fast forward to end of funding period
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      await time.increaseTo(projectDetails.endTime);
      
      // Get project approved
      await openFund.connect(investor3).vote(PROJECT_ID, true); // 500 USDT approve
      await openFund.connect(investor1).vote(PROJECT_ID, true); // 200 USDT approve
    });
    
    it("Should allow raiser to claim funds after approval", async function () {
      const totalFundsRaised = ethers.parseUnits("1000", 6); // 1000 USDT
      const platformFee = (totalFundsRaised * BigInt(PLATFORM_FEE_PERCENT)) / 100n;
      const raiserAmount = totalFundsRaised - platformFee;
      
      const raiserBalanceBefore = await testUSDT.balanceOf(raiser.address);
      
      await openFund.connect(raiser).claimFunds(PROJECT_ID);
      
      const raiserBalanceAfter = await testUSDT.balanceOf(raiser.address);
      expect(raiserBalanceAfter - raiserBalanceBefore).to.equal(raiserAmount);
      
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      expect(projectDetails.fundsClaimed).to.be.true;
      expect(projectDetails.status).to.equal(5); // ProjectStatus.Completed
    });
    
    it("Should not allow non-raiser to claim funds", async function () {
      await expect(
        openFund.connect(investor1).claimFunds(PROJECT_ID)
      ).to.be.revertedWith("Only raiser can claim funds");
    });
    
    it("Should not allow double claiming of funds", async function () {
      await openFund.connect(raiser).claimFunds(PROJECT_ID);
      
      await expect(
        openFund.connect(raiser).claimFunds(PROJECT_ID)
      ).to.be.revertedWith("Funds already claimed");
    });
  });
  
  describe("Platform Fee Claiming", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      await openFund.connect(investor1).invest(PROJECT_ID, 2); // 200 USDT
      await openFund.connect(investor2).invest(PROJECT_ID, 3); // 300 USDT
      await openFund.connect(investor3).invest(PROJECT_ID, 5); // 500 USDT
      
      // Fast forward to end of funding period
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      await time.increaseTo(projectDetails.endTime);
      
      // Get project approved
      await openFund.connect(investor3).vote(PROJECT_ID, true); // 500 USDT approve
      await openFund.connect(investor1).vote(PROJECT_ID, true); // 200 USDT approve
      
      // Raiser claims funds
      await openFund.connect(raiser).claimFunds(PROJECT_ID);
    });
    
    it("Should allow owner to claim platform fee", async function () {
      const totalFundsRaised = ethers.parseUnits("1000", 6); // 1000 USDT
      const platformFee = (totalFundsRaised * BigInt(PLATFORM_FEE_PERCENT)) / 100n;
      
      const ownerBalanceBefore = await testUSDT.balanceOf(owner.address);
      
      await openFund.claimPlatformFee(PROJECT_ID);
      
      const ownerBalanceAfter = await testUSDT.balanceOf(owner.address);
      expect(ownerBalanceAfter - ownerBalanceBefore).to.equal(platformFee);
    });
    
    it("Should not allow non-owner to claim platform fee", async function () {
      await expect(
        openFund.connect(raiser).claimPlatformFee(PROJECT_ID)
      ).to.be.revertedWithCustomError(openFund, "OwnableUnauthorizedAccount");
    });
    
    it("Should not allow double claiming of platform fee", async function () {
      await openFund.claimPlatformFee(PROJECT_ID);
      
      await expect(
        openFund.claimPlatformFee(PROJECT_ID)
      ).to.be.revertedWith("Platform fee already claimed");
    });
  });
  
  describe("Token Claiming", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      await openFund.connect(investor1).invest(PROJECT_ID, 2); // 200 USDT
      await openFund.connect(investor2).invest(PROJECT_ID, 3); // 300 USDT
      await openFund.connect(investor3).invest(PROJECT_ID, 5); // 500 USDT
      
      // Fast forward to end of funding period
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      await time.increaseTo(projectDetails.endTime);
      
      // Get project approved
      await openFund.connect(investor3).vote(PROJECT_ID, true); // 500 USDT approve
      await openFund.connect(investor1).vote(PROJECT_ID, true); // 200 USDT approve
      
      // Raiser claims funds
      await openFund.connect(raiser).claimFunds(PROJECT_ID);
    });
    
    it("Should allow investors to claim tokens", async function () {
      const investmentAmount = ethers.parseUnits("200", 6); // 200 USDT
      const tokensToReceive = investmentAmount / BigInt(TOKEN_PRICE);
      
      const investor1BalanceBefore = await projectToken.balanceOf(investor1.address);
      
      await openFund.connect(investor1).claimTokens(PROJECT_ID);
      
      const investor1BalanceAfter = await projectToken.balanceOf(investor1.address);
      expect(investor1BalanceAfter - investor1BalanceBefore).to.equal(tokensToReceive);
      
      const investmentDetails = await openFund.getInvestmentDetails(PROJECT_ID, investor1.address);
      expect(investmentDetails.hasClaimedTokens).to.be.true;
    });
    
    it("Should not allow non-investors to claim tokens", async function () {
      await expect(
        openFund.connect(owner).claimTokens(PROJECT_ID)
      ).to.be.revertedWith("No investment found");
    });
    
    it("Should not allow double claiming of tokens", async function () {
      await openFund.connect(investor1).claimTokens(PROJECT_ID);
      
      await expect(
        openFund.connect(investor1).claimTokens(PROJECT_ID)
      ).to.be.revertedWith("Tokens already claimed");
    });
  });
  
  describe("Refunds", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      await openFund.connect(investor1).invest(PROJECT_ID, 2); // 200 USDT
      await openFund.connect(investor2).invest(PROJECT_ID, 3); // 300 USDT
      await openFund.connect(investor3).invest(PROJECT_ID, 5); // 500 USDT
      
      // Fast forward to end of funding period
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      await time.increaseTo(projectDetails.endTime);
      
      // Get project rejected
      await openFund.connect(investor3).vote(PROJECT_ID, false); // 500 USDT reject
      await openFund.connect(investor1).vote(PROJECT_ID, false); // 200 USDT reject
    });
    
    it("Should allow investors to get refund after rejection", async function () {
      const investmentAmount = ethers.parseUnits("200", 6); // 200 USDT
      
      const investor1BalanceBefore = await testUSDT.balanceOf(investor1.address);
      
      await openFund.connect(investor1).getRefund(PROJECT_ID);
      
      const investor1BalanceAfter = await testUSDT.balanceOf(investor1.address);
      expect(investor1BalanceAfter - investor1BalanceBefore).to.equal(investmentAmount);
      
      const investmentDetails = await openFund.getInvestmentDetails(PROJECT_ID, investor1.address);
      expect(investmentDetails.hasClaimedRefund).to.be.true; 
    });
    
    it("Should not allow non-investors to get refund", async function () {
      await expect(
        openFund.connect(owner).getRefund(PROJECT_ID)
      ).to.be.revertedWith("No investment found");
    });
    
    it("Should not allow double claiming of refunds", async function () {
      await openFund.connect(investor1).getRefund(PROJECT_ID);
      
      await expect(
        openFund.connect(investor1).getRefund(PROJECT_ID)
      ).to.be.revertedWith("No investment found");
    });
  });
  
  describe("Unsold Tokens", function () {
    beforeEach(async function () {
      await openFund.connect(raiser).depositTokens(PROJECT_ID);
      await openFund.connect(investor1).invest(PROJECT_ID, 2); // 200 USDT
      await openFund.connect(investor2).invest(PROJECT_ID, 3); // 300 USDT
      
      // Fast forward to end of funding period
      const projectDetails = await openFund.getProjectDetails(PROJECT_ID);
      await time.increaseTo(projectDetails.endTime);
    });
    
    it("Should allow raiser to claim unsold tokens", async function () {
      const investmentAmount = ethers.parseUnits("500", 6); // 500 USDT
      const tokensSold = investmentAmount / BigInt(TOKEN_PRICE);
      const unsoldTokens = TOKENS_TO_SELL - tokensSold;

      const raiserBalanceBefore = await projectToken.balanceOf(raiser.address);
      
      await openFund.connect(raiser).claimUnsoldTokens(PROJECT_ID);
      
      const raiserBalanceAfter = await projectToken.balanceOf(raiser.address);
      expect(raiserBalanceAfter - raiserBalanceBefore).to.equal(unsoldTokens);
    });
    
    it("Should not allow non-raiser to claim unsold tokens", async function () {
      await expect(
        openFund.connect(investor1).claimUnsoldTokens(PROJECT_ID)
      ).to.be.revertedWith("Only raiser can claim unsold tokens");
    });
    
    it("Should not allow double claiming of unsold tokens", async function () {
      await openFund.connect(raiser).claimUnsoldTokens(PROJECT_ID);
      
      await expect(
        openFund.connect(raiser).claimUnsoldTokens(PROJECT_ID)
      ).to.be.revertedWith("Unsold tokens claimed");
    });
  });
});
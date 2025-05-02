let web3;
let selectedWallet;
let connectedAccount;
let signature;
let message;
// let nonce;
// nonce = "{{ nonce }}";
// const walletAddressInput = for non investor connecting
// connect_wallet_btn = 
const close_wallet_btn = document.getElementById("close-connect-wallet-btn");
const connect_box = document.getElementById("connect-wallet-box");
const overlay = document.getElementById("overlay");
const loading_spinner = document.getElementById("loading-spinner");

close_wallet_btn.addEventListener("click", function() {
   connect_box.classList.add("hidden");
   overlay.classList.add("hidden");
});

function shortenAddress(address) {
   if (!address) return '';
   return address.slice(0, 6) + '...' + address.slice(-4);
}

const isMetaMaskInstalled = () => {
   return Boolean(window.ethereum && window.ethereum.isMetaMask);
};

const isBinanceWalletInstalled = () => {
   return Boolean(window.ethereum);
};

const isOKXWalletInstalled = () => {
   return Boolean(window.okxwallet);
};

const isTrustWalletInstalled = () => {
   return Boolean(window.trustwallet || (window.ethereum && window.ethereum.isTrust));
};

const isCoinbaseWalletInstalled = () => {
   return Boolean(window.ethereum && window.ethereum.isCoinbaseWallet);
};

async function signMessage(account, message, walletType) {
   try {
      let signedMsg;
      
      switch (walletType) {
            case 'metamask':
            case 'binance':
            case 'coinbase':
               provider = window.ethereum;
               break;
            case 'okx':
               provider = window.okxwallet;
               break;
            case 'trust':
               provider = window.trustwallet || window.ethereum;
               break;
            default:
               throw new Error('Unsupported wallet type');
      }
      
      if (!provider) {
            throw new Error(`${formatWalletName(walletType)} provider not found`);
      }

      signedMsg = await window.ethereum.request({
         method: 'personal_sign',
         params: [message, account]
      });
      
      return signedMsg;
   } catch (error) {
      console.error(`Error signing message with ${walletType}:`, error);
      showToastMessage(`Failed to sign message: ${error.message || 'Unknown error'}`, false);
      return null;
   }
}

async function addSwitchChain(walletType) {
   try {
      let wallet_provider;
      
      switch (walletType) {
            case 'metamask':
            case 'binance':
            case 'coinbase':
               wallet_provider = window.ethereum;
               break;
            case 'okx':
               wallet_provider = window.okxwallet;
               break;
            case 'trust':
               wallet_provider = window.trustwallet || window.ethereum;
               break;
            default:
               throw new Error('Unsupported wallet type');
      }
      
      if (!wallet_provider) {
            throw new Error(`${formatWalletName(walletType)} provider not found`);
      }
      
      try {
            await wallet_provider.request({
               method: 'wallet_switchEthereumChain',
               params: [{ chainId: '0xae3f3' }],
            });
            return true;
      } catch (switchError) {
            await wallet_provider.request({
               method: 'wallet_addEthereumChain',
               params: [{
                  chainId: '0xae3f3',
                  chainName: 'SEI DEVNET',
                  nativeCurrency: {
                        name: 'SEI',
                        symbol: 'SEI',
                        decimals: 18
                  },
                  rpcUrls: ['https://evm-rpc-arctic-1.sei-apis.com'],
                  blockExplorerUrls: ['https://seitrace.com/?chain=arctic-1']
               }],
            });
            
            await wallet_provider.request({
               method: 'wallet_switchEthereumChain',
               params: [{ chainId: '0xae3f3' }],
            });
            return true;
      }
   } catch (error) {
      console.error(`Error adding/switching chain for ${walletType}:`, error);
      showToastMessage(`Failed to set up SEI DEVNET: ${error.message || 'Unknown error'}`, false);
      return false;
   }
}

async function connectWallet(walletType) {
   let accounts = [];
   try {
      switch (walletType) {
         case 'metamask':
            if (!isMetaMaskInstalled()) {
               showToastMessage('MetaMask is not installed. Please install MetaMask first.', false);
               return null;
            }
            accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            break;
            
         case 'binance':
            if (!isBinanceWalletInstalled()) {
               showToastMessage('Binance Wallet is not installed. Please install Binance Wallet first.', false);
               return null;
            }
            accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            break;
            
         case 'okx':
            if (!isOKXWalletInstalled()) {
               showToastMessage('OKX Wallet is not installed. Please install OKX Wallet first.', false);
               return null;
            }
            accounts = await window.okxwallet.request({ method: 'eth_requestAccounts' });
            break;
            
         case 'trust':
            const trustProvider = window.trustwallet || (window.ethereum && window.ethereum.isTrust ? window.ethereum : null);
            if (!trustProvider) {
               showToastMessage('Trust Walle App is not installed. Please install Trust Wallet App first.', false);
               return null;
            }
            accounts = await trustProvider.request({ method: 'eth_requestAccounts' });
            break;
            
         case 'coinbase':
            if (!isCoinbaseWalletInstalled()) {
               showToastMessage('Coinbase Wallet is not installed. Please install Coinbase Wallet first.', false);
               return null;
            }
            accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            break;
      }
      
      return accounts.length > 0 ? accounts[0] : null;
   } catch (error) {
      console.error(`Error connecting to ${walletType}:`, error);
      showToastMessage(`Failed to connect to ${formatWalletName(walletType)}: ${error.message || 'User rejected the request'}`, false);
      return null;
   }
}

function formatWalletName(walletType) {
   const names = {
      'metamask': 'MetaMask',
      'binance': 'Binance Wallet',
      'okx': 'OKX Wallet',
      'trust': 'Trust Wallet',
      'coinbase': 'Coinbase Wallet'
   };
   
   return names[walletType] || walletType;
}

document.querySelectorAll('.wallet_intergrated').forEach(button => {
   button.addEventListener('click', async function() {
      const walletType = this.getAttribute('data-wallet');
      selectedWallet = walletType;
      localStorage.setItem('selectedWallet', walletType);
      loading_spinner.classList.remove("hidden");
      
      try {
         connectedAccount = await connectWallet(walletType);
         
         if (connectedAccount) {
            walletAddressInput.value = shortenAddress(connectedAccount);
            
            message = `Sign this message to verify your wallet ownership with OpenFund. Nonce: ${nonce}`;
            
            const chainSwitched = await addSwitchChain(walletType);
            signature = await signMessage(connectedAccount, message, walletType);
            
            if (signature) {
               //showToastMessage(`Successfully connected to ${formatWalletName(walletType)}`, true);
               if(isInvstorConnecting == true){
                  try {
                     const response = await fetch('/investor-connect', {
                        method: 'POST',
                        headers: {
                           'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                           wallet_address: connectedAccount,
                           signature: signature,
                        })
                     });
                     
                     const data = await response.json();
                     if (data.success) {
                        showToastMessage(data.message, true);
                     } else {
                        showToastMessage(data.message, false);
                     }
                     setTimeout(() => {
                        window.location.reload();
                     }, 1000);
                  } catch (error) {
                     console.error('Error:', error);
                     showToastMessage("An error occurred. Please try again later.", false);
                  } finally {
                     loading_spinner.classList.add("hidden");
                     overlay.classList.add("hidden");
                  }
               }
            } else {
               walletAddressInput.value = '';
            }
         }
      } catch (error) {
         console.error(`Error with ${walletType}:`, error);
         walletAddressInput.value = '';
      } finally {
         loading_spinner.classList.add("hidden");
         connect_box.classList.add("hidden");
         overlay.classList.add("hidden");
      }
   });
});

async function checkWalletConnectionOnLoad() {
   if (investor_wallet_connected) {
     try {
       let provider;
       let isConnected = false;
       
       if (localStorage.getItem('selectedWallet')) {
         const storedWallet = localStorage.getItem('selectedWallet');
         
         switch (storedWallet) {
           case 'metamask':
           case 'binance':
           case 'coinbase':
             if (window.ethereum) {
               provider = window.ethereum;
               const accounts = await provider.request({ method: 'eth_accounts' });
               isConnected = accounts && accounts.length > 0;
             }
             break;
           case 'okx':
             if (window.okxwallet) {
               provider = window.okxwallet;
               const accounts = await provider.request({ method: 'eth_accounts' });
               isConnected = accounts && accounts.length > 0;
             }
             break;
           case 'trust':
             provider = window.trustwallet || (window.ethereum && window.ethereum.isTrust ? window.ethereum : null);
             if (provider) {
               const accounts = await provider.request({ method: 'eth_requestAccounts' });
               //const accounts = await provider.request({ method: 'eth_accounts' });
               isConnected = accounts && accounts.length > 0;
             }
             break;
         }
       }
       if (!isConnected) {
         localStorage.removeItem('selectedWallet');
         window.location.href = '/disconnect';
       } else {
         const event = new CustomEvent('walletConnectionVerified', { detail: { isConnected: true } });
         window.dispatchEvent(event);
       }
     } catch (error) {
       console.error('Error checking wallet connection:', error);
       window.location.href = '/disconnect';
     }
   }
 }
 window.addEventListener('DOMContentLoaded', () => {
   checkWalletConnectionOnLoad();
 });

//connect
const connect_wallet_btn = document.getElementById("connect-btn");
const walletAddressInput = document.getElementById("investor-wallet-address");
const investor_account_manage = document.getElementById("investor-account-manage");
const raiser_account_btn = document.getElementById("raiser-account");
const raiser_account_manage = document.getElementById("raiser-account-manage");
const sign_in_up_btn = document.getElementById("sign-in-up-btn");
const investor_disconnect_btn = document.getElementById("investor-disconnect-btn");
const investor_connected_check = document.getElementById("investor_connected_check");

investor_disconnect_btn.addEventListener('click', async function() {
   try {
      await window.ethereum.request({
         method: 'wallet_revokePermissions',
         params: [
            {
               eth_accounts: {},
            },
         ],
      });
   } catch (e) {
      console.log(e);
   }
   window.location.href = '/disconnect';
});

raiser_account_btn.addEventListener("click", function() {
   raiser_account_manage.classList.remove('hidden');
});
connect_wallet_btn.addEventListener("click", function() {
   if (investor_wallet_connected) {
         investor_account_manage.classList.remove('hidden');
      } else {
         connect_box.classList.remove("hidden");
         overlay.classList.remove("hidden");
      }
});

document.addEventListener("click", function(event) {
   if (
      !investor_account_manage.contains(event.target) &&
      !connect_wallet_btn.contains(event.target)
   ) {
      investor_account_manage.classList.add('hidden');
   }
   
   if (
      !raiser_account_manage.contains(event.target) &&
      !raiser_account_btn.contains(event.target)
   ) {
      raiser_account_manage.classList.add('hidden');
   }
});

if (investor_wallet_connected) {
   investor_connected_check.classList.remove('hidden');
   walletAddressInput.value = shortWallet;
}

if (raiser_loggedin) {
   raiser_account_btn.classList.remove('hidden');
   sign_in_up_btn.classList.add('hidden');
} else {
   investor_account_manage.style.right = "-50px";
}
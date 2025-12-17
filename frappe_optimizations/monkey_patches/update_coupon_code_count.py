BOOKKEEPER_HOST = "http://localhost:8092"
API_PREFIX = "/api/book-keeper/v1"
TENANT_ID = "twophasetenant"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def update_coupon_code_count(coupon_name, transaction_type):
	"""
	Uses book-keeper API for two-phase commit of coupon code counting.
	Creates pending journal entry, commits on success, voids on rollback.
	"""
	import uuid
	from datetime import date

	import requests

	COUPON_DEBIT_ACCOUNT = f"coupon_used_{coupon_name}"
	COUPON_CREDIT_ACCOUNT = f"coupon_available_{coupon_name}"

	if transaction_type == "used":
		request_id = uuid.uuid4().hex
		idempotency_key = f"coupon_{coupon_name}_{request_id}"

		pending_payload = {
			"tenant_id": TENANT_ID,
			"idempotency_key": idempotency_key,
			"entry_date": str(date.today()),
			"narration": f"Coupon usage: {coupon_name}",
			"debit_legs": [{"account_code": COUPON_DEBIT_ACCOUNT, "amount": 1, "currency": "USD"}],
			"credit_legs": [{"account_code": COUPON_CREDIT_ACCOUNT, "amount": 1, "currency": "USD"}],
			"timeout_seconds": 300,
		}

		response = requests.post(
			f"{BOOKKEEPER_HOST}{API_PREFIX}/pending-journal-entries",
			json=pending_payload,
			headers=HEADERS,
			timeout=5,
		)
		response.raise_for_status()
		journal_id = response.json()["journal_id"]

		commit_response = requests.post(
			f"{BOOKKEEPER_HOST}{API_PREFIX}/pending-journal-entries/{journal_id}/commit",
			json={"tenant_id": TENANT_ID},
			headers=HEADERS,
			timeout=5,
		)
		commit_response.raise_for_status()
		print(f"[BOOK-KEEPER] Committed journal entry {journal_id} for coupon {coupon_name}")

	elif transaction_type == "cancelled":
		idempotency_key = f"coupon_cancel_{coupon_name}_{uuid.uuid4().hex}"

		reversal_payload = {
			"tenant_id": TENANT_ID,
			"idempotency_key": idempotency_key,
			"entry_date": str(date.today()),
			"narration": f"Coupon cancellation: {coupon_name}",
			"debit_legs": [{"account_code": COUPON_CREDIT_ACCOUNT, "amount": 1, "currency": "USD"}],
			"credit_legs": [{"account_code": COUPON_DEBIT_ACCOUNT, "amount": 1, "currency": "USD"}],
		}

		response = requests.post(
			f"{BOOKKEEPER_HOST}{API_PREFIX}/journal-entries",
			json=reversal_payload,
			headers=HEADERS,
			timeout=5,
		)
		response.raise_for_status()
		print(f"[BOOK-KEEPER] Cancelled coupon {coupon_name}")


def create_bookkeeper_coupon_accounts(coupon_name, maximum_use=None):
	"""
	Create coupon accounts in book-keeper.
	Call this function when creating a new Coupon Code in Frappe.

	Args:
		coupon_name: The name/code of the coupon
		maximum_use: Maximum number of times coupon can be used (None = unlimited)

	Returns:
		dict: Response from book-keeper API

	Example:
		create_bookkeeper_coupon_accounts("SAVE20", maximum_use=1000)
	"""
	import requests

	COUPON_DEBIT_ACCOUNT = f"coupon_used_{coupon_name}"
	COUPON_CREDIT_ACCOUNT = f"coupon_available_{coupon_name}"

	accounts_payload = {
		"tenant_id": TENANT_ID,
		"accounts": [
			{"code": COUPON_DEBIT_ACCOUNT, "name": f"Coupon Used: {coupon_name}", "type": "asset"},
			{
				"code": COUPON_CREDIT_ACCOUNT,
				"name": f"Coupon Available: {coupon_name}",
				"type": "liability",
				"max_balance": maximum_use if maximum_use else 999999,
			},
		],
	}

	response = requests.post(
		f"{BOOKKEEPER_HOST}{API_PREFIX}/accounts",
		json=accounts_payload,
		headers=HEADERS,
		timeout=5,
	)
	response.raise_for_status()
	print(f"Created book-keeper accounts for coupon: {coupon_name}")
	return response.json()


def get_coupon_usage_from_bookkeeper(coupon_name):
	"""
	Get coupon usage count from book-keeper (source of truth).
	Use this instead of reading from Frappe DB.

	Args:
		coupon_name: The name/code of the coupon

	Returns:
		int: Number of times coupon has been used

	Example:
		used_count = get_coupon_usage_from_bookkeeper("SAVE20")
	"""
	import requests

	COUPON_DEBIT_ACCOUNT = f"coupon_used_{coupon_name}"

	balance_response = requests.get(
		f"{BOOKKEEPER_HOST}{API_PREFIX}/accounts/balances",
		params={"tenant_id": TENANT_ID, "account_codes": COUPON_DEBIT_ACCOUNT},
		headers=HEADERS,
		timeout=5,
	)
	balance_response.raise_for_status()
	balances = balance_response.json()

	if balances and len(balances) > 0:
		used_count = int(abs(balances[0].get("balance", 0)))
		return used_count
	else:
		return 0


def test_bookkeeper_coupon_flow(coupon_name="TEST-COUPON", maximum_use=10, parallel_requests=5, iterations=1):
	"""
	Test the update_coupon_code_count function with book-keeper integration.
	Tests parallel coupon usage to verify concurrency handling.

	Usage:
		bench execute frappe_optimizations.monkey_patches.update_coupon_code_count.test_bookkeeper_coupon_flow
		bench execute "frappe_optimizations.monkey_patches.update_coupon_code_count.test_bookkeeper_coupon_flow('SAVE20', 100, 10, 20)"

	Tests:
		1. Create accounts in book-keeper
		2. Test parallel coupon usage (simulating concurrent requests)
		3. Verify final count matches expected usage
	"""
	import concurrent.futures
	import time

	print("\n" + "=" * 60)
	print(f"[TEST] Testing update_coupon_code_count for: {coupon_name}")
	print(f"[TEST] Parallel requests: {parallel_requests} x {iterations} iterations")
	print("=" * 60)

	print(f"\n[STEP 1] Creating book-keeper accounts for {coupon_name}...")
	create_bookkeeper_coupon_accounts(coupon_name, maximum_use)
	print("✅ Accounts created successfully")

	print("\n[STEP 2] Getting initial balance...")
	initial_count = get_coupon_usage_from_bookkeeper(coupon_name)
	print(f"✅ Initial usage count: {initial_count}")

	print(f"\n[STEP 3] Testing {parallel_requests} parallel coupon usages x {iterations} iterations...")
	start_time = time.time()

	def use_coupon(index):
		update_coupon_code_count(coupon_name, "used")
		return index

	total_requests = 0
	for iteration in range(iterations):
		with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_requests) as executor:
			futures = [executor.submit(use_coupon, i) for i in range(parallel_requests)]
			results = [future.result() for future in concurrent.futures.as_completed(futures)]
			total_requests += len(results)
		print(f"  Iteration {iteration + 1}/{iterations} completed ({len(results)} requests)")

	elapsed_time = time.time() - start_time
	print(f"✅ {total_requests} total requests completed in {elapsed_time:.2f} seconds")

	print("\n[STEP 4] Checking final balance...")
	final_count = get_coupon_usage_from_bookkeeper(coupon_name)
	print(f"✅ Final usage count: {final_count}")

	expected_count = initial_count + total_requests
	assert final_count == expected_count, f"Expected {expected_count}, got {final_count}"

	print("\n" + "=" * 60)
	print("✅ ALL TESTS PASSED!")
	print(f"   Initial count: {initial_count}")
	print(f"   Total requests: {total_requests} ({parallel_requests} x {iterations})")
	print(f"   Final count: {final_count}")
	print(f"   Time taken: {elapsed_time:.2f}s")
	print(f"   Avg per request: {elapsed_time / total_requests:.3f}s")
	print("=" * 60 + "\n")


# if __name__ == "__main__":
# 	test_bookkeeper_coupon_flow(parallel_requests=10, iterations=10)


def update_coupon_code_count_monkey_patch():
	# nosemgrep
	from erpnext.accounts.doctype.pricing_rule import utils

	utils.update_coupon_code_count = update_coupon_code_count  # nosemgrep

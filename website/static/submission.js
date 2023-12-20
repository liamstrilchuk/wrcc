window.addEventListener("load", async () => {
	const submissionId = window.location.pathname.split("/").pop();
	const response = await fetch("/api/submission/" + submissionId);
	const submission = await response.json();

	const codeElement = document.getElementById("submissionCode");
	codeElement.innerText = submission.code;
})
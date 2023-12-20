function formatDate(date) {
	const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

	return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function pad(num) {
	return num.toString().padStart(2, "0");
}
const form = document.getElementById("admissionForm");
const result = document.getElementById("result");

form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const data = {
        student_name: document.getElementById("student_name").value.trim(),
        father_name: document.getElementById("father_name").value.trim(),
        mother_name: document.getElementById("mother_name").value.trim(),
        date_of_birth: document.getElementById("date_of_birth").value,
        gender: document.getElementById("gender").value,
        applying_class: document.getElementById("applying_class").value,
        previous_school: document.getElementById("previous_school").value.trim(),
        parent_cnic: document.getElementById("parent_cnic").value.trim(),
        student_cnic: document.getElementById("student_cnic").value.trim(),
        phone: document.getElementById("phone").value.trim(),
        whatsapp: document.getElementById("whatsapp").value.trim(),
        email: document.getElementById("email").value.trim(),
        address: document.getElementById("address").value.trim()
    };

    result.className = "";
    result.style.display = "none";

    try {
        const response = await fetch("/api/admissions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });

        const responseData = await response.json();

        if (!response.ok) {
            throw new Error(
                responseData.detail || "Admission submission failed"
            );
        }

        result.style.display = "block";
        result.className = "result-success";

        result.innerHTML = `
            <strong>Application Submitted Successfully ✅</strong>
            <br><br>

            Application Number:
            <strong>${responseData.application_no}</strong>

            <br>

            Student:
            ${responseData.student_name}

            <br>

            Status:
            ${responseData.status}
        `;

        form.reset();

    } catch (error) {
        console.error("Submission Error:", error);

        result.style.display = "block";
        result.className = "result-error";

        result.innerHTML = `
            <strong>Submission Failed</strong>
            <br>
            ${error.message}
        `;
    }
});
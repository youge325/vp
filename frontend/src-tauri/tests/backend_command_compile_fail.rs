#[test]
fn sealed_backend_specs_reject_another_commands_invocation() {
    let cases = trybuild::TestCases::new();
    cases.compile_fail("tests/ui/backend_command_wrong_invocation.rs");
    cases.compile_fail("tests/ui/backend_command_unsealed_spec.rs");
}

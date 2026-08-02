import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, extname, relative, resolve } from 'node:path'
import process from 'node:process'
import ts from 'typescript'
import { compileTemplate, parse as parseVueSfc } from 'vue/compiler-sfc'
import {
  AMBIENT_SOURCE_ALLOWLIST,
  GENERATED_SOURCE_ALLOWLIST,
  KNIP_DEPENDENCY_ALLOWLIST,
} from './quality-allowlists.mjs'
import { collectUnreachableModules } from './production-reachability.mjs'

const sourceRoot = resolve(process.cwd(), 'src')
const e2eRoot = resolve(process.cwd(), 'tests/e2e')
const sourceExtensions = new Set(['.ts', '.tsx', '.vue'])

function walk(directory) {
  return readdirSync(directory)
    .flatMap((name) => {
      const path = resolve(directory, name)
      return statSync(path).isDirectory() ? walk(path) : [path]
    })
    .filter((path) => sourceExtensions.has(path.slice(path.lastIndexOf('.'))))
}

const sourceFiles = walk(sourceRoot)
const modulePaths = new Map()
const portInterfacePattern = /(?:Port|Capability|Continuation|Operations)$/

function parseTypeScriptSources(paths) {
  return paths.flatMap((path) => parseTypeScriptSourcesFromText(path, readFileSync(path, 'utf8')))
}

function parseTypeScriptSourcesFromText(path, source) {
  const extension = extname(path)
  if (['.ts', '.tsx'].includes(extension)) {
    return [createTypeScriptEntry(path, path, source)]
  }
  if (extension !== '.vue') {
    return []
  }

  const descriptor = parseVueDescriptor(path, source)
  return [descriptor.script, descriptor.scriptSetup]
    .filter(Boolean)
    .sort((left, right) => left.loc.start.offset - right.loc.start.offset)
    .flatMap((block, index) => {
      const language = block.lang?.toLowerCase()
      return language === 'ts' || language === 'tsx'
        ? [createTypeScriptEntry(`${path}.${index}.${language}`, path, block.content)]
        : []
    })
}

function parseVueDescriptor(path, source) {
  const { descriptor, errors } = parseVueSfc(source, { filename: path })
  if (errors.length > 0) {
    const messages = errors.map((error) => error instanceof Error ? error.message : String(error))
    throw new Error(`Unable to parse ${path}: ${messages.join('; ')}`)
  }
  return descriptor
}

function compileVueTemplate(path, source) {
  const descriptor = parseVueDescriptor(path, source)
  if (!descriptor.template) {
    return ''
  }
  const result = compileTemplate({
    id: `architecture-${normalizedPath(path)}`,
    filename: path,
    source: descriptor.template.content,
  })
  if (result.errors.length > 0) {
    const messages = result.errors.map((error) => error instanceof Error ? error.message : String(error))
    throw new Error(`Unable to compile template ${path}: ${messages.join('; ')}`)
  }
  return result.code
}

function createTypeScriptEntry(path, ownerPath, source) {
  return {
    path,
    ownerPath,
    sourceFile: ts.createSourceFile(
      path,
      source,
      ts.ScriptTarget.Latest,
      true,
      extname(path) === '.tsx' ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    ),
  }
}

function declaredName(node) {
  if (node && (ts.isIdentifier(node) || ts.isStringLiteral(node))) {
    return node.text
  }
  return null
}

function normalizedPath(path) {
  return resolve(path).replaceAll('\\', '/')
}

function createTypeScriptProgram(entries, compilerOptions = {}) {
  const options = {
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    target: ts.ScriptTarget.ESNext,
    strict: true,
    ...compilerOptions,
  }
  const entriesByPath = new Map(entries.map((entry) => [normalizedPath(entry.path), entry]))
  const host = ts.createCompilerHost(options)
  const fileExists = host.fileExists.bind(host)
  const readFile = host.readFile.bind(host)
  const getSourceFile = host.getSourceFile.bind(host)
  host.fileExists = (path) => entriesByPath.has(normalizedPath(path)) || fileExists(path)
  host.readFile = (path) => entriesByPath.get(normalizedPath(path))?.sourceFile.text ?? readFile(path)
  host.getSourceFile = (path, languageVersion, onError, shouldCreateNewSourceFile) => (
    entriesByPath.get(normalizedPath(path))?.sourceFile
      ?? getSourceFile(path, languageVersion, onError, shouldCreateNewSourceFile)
  )
  return ts.createProgram({ rootNames: entries.map(({ path }) => path), options, host })
}

function collectUnusedPortMembers(program, productionPaths, ownerPaths = new Map()) {
  const declarations = []
  const inheritedPortDeclarations = []
  const consumedDeclarations = new Set()
  const checker = program.getTypeChecker()
  const normalizedProductionPaths = new Set(
    productionPaths.map(normalizedPath),
  )
  const sources = program.getSourceFiles().filter((sourceFile) => (
    normalizedProductionPaths.has(normalizedPath(sourceFile.fileName))
  ))

  for (const sourceFile of sources) {
    for (const statement of sourceFile.statements) {
      const members = ts.isInterfaceDeclaration(statement)
        ? statement.members
        : ts.isTypeAliasDeclaration(statement) && ts.isTypeLiteralNode(statement.type)
          ? statement.type.members
          : null
      if (!members || !portInterfacePattern.test(statement.name.text)) {
        continue
      }
      if (ts.isInterfaceDeclaration(statement) && statement.heritageClauses?.length) {
        inheritedPortDeclarations.push({
          path: ownerPaths.get(normalizedPath(sourceFile.fileName)) ?? sourceFile.fileName,
          interfaceName: statement.name.text,
          name: '<inherited-port-members>',
        })
      }
      for (const member of members) {
        const name = declaredName(member.name)
        if (name) {
          declarations.push({
            path: ownerPaths.get(normalizedPath(sourceFile.fileName)) ?? sourceFile.fileName,
            interfaceName: statement.name.text,
            member,
            name,
          })
        }
      }
    }
  }

  const consumeSymbol = (symbol) => {
    for (const rootSymbol of symbol ? checker.getRootSymbols(symbol) : []) {
      for (const declaration of rootSymbol.declarations ?? []) {
        consumedDeclarations.add(declaration)
      }
    }
  }

  consumePropertyReferences(sources, checker, consumeSymbol, (owner) => (
    ts.isVariableDeclaration(owner) && owner.initializer ? owner.initializer : owner
  ))

  return [
    ...inheritedPortDeclarations,
    ...declarations
      .filter(({ member }) => !consumedDeclarations.has(member))
      .map(({ path, interfaceName, name }) => ({ path, interfaceName, name })),
  ]
}

function rootDeclarations(checker, symbol) {
  return (symbol ? checker.getRootSymbols(symbol) : [])
    .flatMap((rootSymbol) => rootSymbol.declarations ?? [])
}

function consumePropertyReferences(sources, checker, consumeSymbol, bindingSource) {
  for (const sourceFile of sources) {
    function visit(node) {
      if (ts.isPropertyAccessExpression(node)) {
        consumeSymbol(checker.getSymbolAtLocation(node.name))
      } else if (
        ts.isElementAccessExpression(node)
        && node.argumentExpression
        && ts.isStringLiteral(node.argumentExpression)
      ) {
        consumeSymbol(checker.getPropertyOfType(checker.getTypeAtLocation(node.expression), node.argumentExpression.text))
      } else if (
        ts.isBindingElement(node)
        && ts.isObjectBindingPattern(node.parent)
        && !node.dotDotDotToken
      ) {
        const name = declaredName(node.propertyName ?? node.name)
        const source = bindingSource(node.parent.parent)
        if (name && source) {
          consumeSymbol(checker.getPropertyOfType(checker.getTypeAtLocation(source), name))
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(sourceFile)
  }
}

function directReturnObjects(functionNode) {
  if (ts.isArrowFunction(functionNode) && ts.isObjectLiteralExpression(functionNode.body)) {
    return [functionNode.body]
  }
  if (!ts.isBlock(functionNode.body)) {
    return []
  }
  const objects = []
  function visit(node) {
    if (node !== functionNode.body && ts.isFunctionLike(node)) {
      return
    }
    if (ts.isReturnStatement(node) && node.expression && ts.isObjectLiteralExpression(node.expression)) {
      objects.push(node.expression)
      return
    }
    ts.forEachChild(node, visit)
  }
  visit(functionNode.body)
  return objects
}

function exportedFactoryFunctions(sourceFile) {
  const factories = []
  for (const statement of sourceFile.statements) {
    const exported = statement.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword)
    if (!exported) {
      continue
    }
    if (ts.isFunctionDeclaration(statement) && statement.name?.text.startsWith('use') && statement.body) {
      factories.push({ name: statement.name.text, functionNode: statement })
      continue
    }
    if (!ts.isVariableStatement(statement)) {
      continue
    }
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || !declaration.name.text.startsWith('use') || !declaration.initializer) {
        continue
      }
      const initializer = declaration.initializer
      if (ts.isArrowFunction(initializer) || ts.isFunctionExpression(initializer)) {
        factories.push({ name: declaration.name.text, functionNode: initializer })
        continue
      }
      if (
        ts.isCallExpression(initializer)
        && ts.isIdentifier(initializer.expression)
        && initializer.expression.text === 'defineStore'
      ) {
        const setup = [...initializer.arguments].reverse().find((argument) => (
          ts.isArrowFunction(argument) || ts.isFunctionExpression(argument)
        ))
        if (setup) {
          factories.push({ name: declaration.name.text, functionNode: setup })
        }
      }
    }
  }
  return factories
}

function collectUnusedReturnedMembers(
  program,
  productionPaths,
  ownerPaths = new Map(),
  templateSources = new Map(),
) {
  const checker = program.getTypeChecker()
  const normalizedProductionPaths = new Set(productionPaths.map(normalizedPath))
  const sources = program.getSourceFiles().filter((sourceFile) => (
    normalizedProductionPaths.has(normalizedPath(sourceFile.fileName))
  ))
  const declarations = []
  const consumedDeclarations = new Set()

  for (const sourceFile of sources) {
    for (const factory of exportedFactoryFunctions(sourceFile)) {
      const signature = checker.getSignatureFromDeclaration(factory.functionNode)
      const returnType = signature ? checker.getReturnTypeOfSignature(signature) : undefined
      for (const object of directReturnObjects(factory.functionNode)) {
        for (const property of object.properties) {
          if (ts.isSpreadAssignment(property)) {
            continue
          }
          const name = declaredName(property.name)
          if (!name) {
            continue
          }
          const symbol = returnType ? checker.getPropertyOfType(returnType, name) : undefined
          const roots = new Set(rootDeclarations(checker, symbol))
          if (roots.size > 0) {
            declarations.push({
              factoryName: factory.name,
              memberName: name,
              ownerPath: ownerPaths.get(normalizedPath(sourceFile.fileName)) ?? sourceFile.fileName,
              roots,
            })
          }
        }
      }
    }
  }

  const consumeSymbol = (symbol) => {
    for (const declaration of rootDeclarations(checker, symbol)) {
      consumedDeclarations.add(declaration)
    }
  }

  consumePropertyReferences(sources, checker, consumeSymbol, (owner) => (
    ts.isVariableDeclaration(owner) ? owner.initializer : undefined
  ))

  for (const sourceFile of sources) {
    const ownerPath = ownerPaths.get(normalizedPath(sourceFile.fileName))
    const template = ownerPath ? templateSources.get(normalizedPath(ownerPath)) : undefined
    if (!template) {
      continue
    }
    const receivers = new Map()
    function collectReceivers(node) {
      if (
        ts.isVariableDeclaration(node)
        && ts.isIdentifier(node.name)
        && node.initializer
      ) {
        receivers.set(node.name.text, checker.getTypeAtLocation(node.initializer))
      }
      ts.forEachChild(node, collectReceivers)
    }
    collectReceivers(sourceFile)
    for (const match of template.matchAll(/\b_ctx\.([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)/gu)) {
      const receiverType = receivers.get(match[1])
      if (receiverType) {
        consumeSymbol(checker.getPropertyOfType(receiverType, match[2]))
      }
    }
  }

  return declarations
    .filter(({ roots }) => ![...roots].some((root) => consumedDeclarations.has(root)))
    .map(({ factoryName, memberName, ownerPath }) => ({ factoryName, memberName, ownerPath }))
}

function collectModuleSpecifiers(entries) {
  const specifiers = []
  for (const { sourceFile } of entries) {
    function visit(node) {
      if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
        specifiers.push(node.moduleSpecifier.text)
      } else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        specifiers.push(node.moduleSpecifier.text)
      } else if (
        ts.isCallExpression(node)
        && node.expression.kind === ts.SyntaxKind.ImportKeyword
        && node.arguments.length === 1
        && ts.isStringLiteral(node.arguments[0])
      ) {
        specifiers.push(node.arguments[0].text)
      }
      ts.forEachChild(node, visit)
    }
    visit(sourceFile)
  }
  return specifiers
}

function isGeneratedTypeSource(sourceFile) {
  const path = normalizedPath(sourceFile.fileName)
  if (!path.startsWith(`${normalizedPath(sourceRoot)}/`)) {
    return false
  }
  return path.includes('/types/generated/')
    || /^\/\* Generated from contracts\/[^\n]+\. Do not edit\. \*\//u.test(sourceFile.text)
}

function resolveGeneratedType(checker, node) {
  let symbol = checker.getSymbolAtLocation(node)
  const visited = new Set()
  while (symbol && (symbol.flags & ts.SymbolFlags.Alias) !== 0 && !visited.has(symbol)) {
    visited.add(symbol)
    symbol = checker.getAliasedSymbol(symbol)
  }
  const generatedDeclaration = symbol?.declarations?.find((declaration) => (
    isGeneratedTypeSource(declaration.getSourceFile())
  ))
  return generatedDeclaration ? symbol.getName() : null
}

function collectGeneratedMirrorAliases(program, productionPaths, ownerPaths = new Map()) {
  const mirrors = []
  const checker = program.getTypeChecker()
  const normalizedProductionPaths = new Set(productionPaths.map(normalizedPath))
  const sources = program.getSourceFiles().filter((sourceFile) => (
    normalizedProductionPaths.has(normalizedPath(sourceFile.fileName))
  ))
  for (const sourceFile of sources) {
    if (isGeneratedTypeSource(sourceFile)) {
      continue
    }
    const path = ownerPaths.get(normalizedPath(sourceFile.fileName)) ?? sourceFile.fileName
    for (const statement of sourceFile.statements) {
      if (
        ts.isTypeAliasDeclaration(statement)
        && ts.isTypeReferenceNode(statement.type)
        && !statement.type.typeArguments?.length
      ) {
        const target = ts.isQualifiedName(statement.type.typeName)
          ? statement.type.typeName.right
          : statement.type.typeName
        const generated = resolveGeneratedType(checker, target)
        if (generated) {
          mirrors.push({ path, alias: statement.name.text, generated })
        }
      }
      if (ts.isExportDeclaration(statement) && statement.exportClause && ts.isNamedExports(statement.exportClause)) {
        for (const element of statement.exportClause.elements) {
          const generated = resolveGeneratedType(checker, element.propertyName ?? element.name)
            ?? resolveGeneratedType(checker, element.name)
          if (generated && element.name.text !== generated) {
            mirrors.push({ path, alias: element.name.text, generated })
          }
        }
      }
    }
  }
  return mirrors
}

function runArchitectureRuleSelfTests() {
  const fixtureRoot = resolve(process.cwd(), 'scripts/fixtures/architecture')
  const fixture = (name, kind = 'ts') => {
    const fixturePath = resolve(fixtureRoot, name)
    const path = `${fixturePath}.${kind}`
    const source = readFileSync(fixturePath, 'utf8')
    if (kind === 'vue') {
      const entries = parseTypeScriptSourcesFromText(path, source)
      if (entries.length !== 1) {
        throw new Error(`${name} must contain exactly one TypeScript Vue script`)
      }
      return entries[0]
    }
    return createTypeScriptEntry(path, path, source)
  }
  const unusedFixture = fixture('unused-port-member.fixture')
  const fixtureProgram = (entry) => {
    const options = {
      module: ts.ModuleKind.ESNext,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      target: ts.ScriptTarget.ESNext,
      strict: true,
      baseUrl: process.cwd(),
      paths: { '@/*': ['./src/*'] },
    }
    return createTypeScriptProgram([entry], options)
  }
  const unused = collectUnusedPortMembers(fixtureProgram(unusedFixture), [unusedFixture.path])
  if (unused.length !== 1 || unused[0].name !== 'unused') {
    throw new Error(`unused port member self-test did not reject only the unconsumed member: ${JSON.stringify(unused)}`)
  }
  const unusedReturnedFixture = fixture('unused-returned-member.fixture')
  const unusedReturned = collectUnusedReturnedMembers(
    fixtureProgram(unusedReturnedFixture),
    [unusedReturnedFixture.path],
  )
  if (unusedReturned.length !== 1 || unusedReturned[0].memberName !== 'unused') {
    throw new Error(
      `returned member self-test did not reject only the unconsumed member: ${JSON.stringify(unusedReturned)}`,
    )
  }
  const usedReturnedFixture = fixture('used-returned-members.fixture')
  if (
    collectUnusedReturnedMembers(
      fixtureProgram(usedReturnedFixture),
      [usedReturnedFixture.path],
    ).length !== 0
  ) {
    throw new Error('returned member self-test rejected a production destructure')
  }
  const templateFixturePath = resolve(fixtureRoot, 'used-returned-member-template.fixture.vue')
  const templateFixtureSource = readFileSync(
    resolve(fixtureRoot, 'used-returned-member-template.fixture'),
    'utf8',
  )
  const templateFixture = parseTypeScriptSourcesFromText(templateFixturePath, templateFixtureSource)[0]
  if (
    collectUnusedReturnedMembers(
      fixtureProgram(templateFixture),
      [templateFixture.path],
      new Map([[normalizedPath(templateFixture.path), templateFixturePath]]),
      new Map([[normalizedPath(templateFixturePath), compileVueTemplate(templateFixturePath, templateFixtureSource)]]),
    ).length !== 0
  ) {
    throw new Error('returned member self-test rejected a Vue template consumer')
  }
  const usedFixture = fixture('used-port-member.fixture')
  if (collectUnusedPortMembers(fixtureProgram(usedFixture), [usedFixture.path]).length !== 0) {
    throw new Error('used port member self-test rejected a production consumer')
  }
  const unrelatedFixture = fixture('unrelated-port-member.fixture')
  const unrelated = collectUnusedPortMembers(fixtureProgram(unrelatedFixture), [unrelatedFixture.path])
  if (unrelated.length !== 1 || unrelated[0].name !== 'unused') {
    throw new Error('unrelated same-name property incorrectly kept a port member alive')
  }
  const typeAliasFixture = fixture('unused-port-type-alias.fixture')
  const typeAliasUnused = collectUnusedPortMembers(
    fixtureProgram(typeAliasFixture),
    [typeAliasFixture.path],
  )
  if (typeAliasUnused.length !== 1 || typeAliasUnused[0].name !== 'unused') {
    throw new Error('object type alias port self-test did not reject its unconsumed member')
  }
  const inheritedFixture = fixture('inherited-port-member.fixture')
  const inherited = collectUnusedPortMembers(
    fixtureProgram(inheritedFixture),
    [inheritedFixture.path],
  )
  if (
    inherited.length !== 1
    || inherited[0].interfaceName !== 'DerivedPort'
    || inherited[0].name !== '<inherited-port-members>'
  ) {
    throw new Error('port heritage self-test did not reject inherited members')
  }
  const mirrorFixture = fixture('generated-mirror-alias.fixture')
  const mirrors = collectGeneratedMirrorAliases(fixtureProgram(mirrorFixture), [mirrorFixture.path])
  if (mirrors.length !== 1 || mirrors[0].alias !== 'MirroredError') {
    throw new Error('generated mirror alias self-test did not reject the direct alias')
  }
  const sameNameMirrorFixture = fixture('generated-same-name-mirror-alias.fixture')
  const sameNameMirrors = collectGeneratedMirrorAliases(
    fixtureProgram(sameNameMirrorFixture),
    [sameNameMirrorFixture.path],
  )
  if (
    sameNameMirrors.length !== 1
    || sameNameMirrors[0].alias !== 'TaskErrorPayload'
    || sameNameMirrors[0].generated !== 'TaskErrorPayload'
  ) {
    throw new Error('generated mirror alias self-test did not reject a same-name imported alias')
  }
  const localFixture = fixture('generated-local-same-name.fixture')
  if (collectGeneratedMirrorAliases(fixtureProgram(localFixture), [localFixture.path]).length !== 0) {
    throw new Error('generated mirror alias self-test rejected a local same-name type')
  }
  const namespaceFixture = fixture('generated-namespace-alias.fixture')
  const namespaceMirrors = collectGeneratedMirrorAliases(
    fixtureProgram(namespaceFixture),
    [namespaceFixture.path],
  )
  if (namespaceMirrors.length !== 1 || namespaceMirrors[0].alias !== 'NamespacedError') {
    throw new Error('generated mirror alias self-test did not reject a namespace import alias')
  }
  const eventFixture = fixture('generated-event-alias.fixture')
  const eventMirrors = collectGeneratedMirrorAliases(fixtureProgram(eventFixture), [eventFixture.path])
  if (eventMirrors.length !== 1 || eventMirrors[0].generated !== 'TaskEventPayloadMap') {
    throw new Error('generated mirror alias self-test did not recognize generated event types')
  }
  const vueFixture = fixture('generated-vue-alias.fixture', 'vue')
  const vueMirrors = collectGeneratedMirrorAliases(fixtureProgram(vueFixture), [vueFixture.path])
  if (vueMirrors.length !== 1 || vueMirrors[0].alias !== 'VueErrorMirror') {
    throw new Error('generated mirror alias self-test did not inspect Vue TypeScript scripts')
  }
  const derivedFixture = fixture('generated-derived-type.fixture')
  if (
    collectGeneratedMirrorAliases(fixtureProgram(derivedFixture), [derivedFixture.path]).length !== 0
  ) {
    throw new Error('generated mirror alias self-test rejected a derived type')
  }
  const exportFixture = fixture('generated-export-alias.fixture')
  const exportMirrors = collectGeneratedMirrorAliases(fixtureProgram(exportFixture), [exportFixture.path])
  if (exportMirrors.length !== 3) {
    throw new Error('generated mirror alias self-test did not reject export aliases')
  }
}

runArchitectureRuleSelfTests()

for (const path of sourceFiles) {
  const owner = relative(sourceRoot, path).replaceAll('\\', '/')
  const withoutExtension = owner.slice(0, -extname(owner).length)
  const candidates = [owner, withoutExtension]
  if (withoutExtension.endsWith('/index')) {
    candidates.push(withoutExtension.slice(0, -'/index'.length))
  }
  for (const candidate of candidates) {
    modulePaths.set(candidate, owner)
  }
}

function resolveInternalImport(ownerPath, dependency) {
  let candidate
  if (dependency.startsWith('@/')) {
    candidate = dependency.slice(2)
  } else if (dependency.startsWith('.')) {
    const absolute = resolve(dirname(ownerPath), dependency)
    candidate = relative(sourceRoot, absolute).replaceAll('\\', '/')
  } else {
    return null
  }

  for (const path of [
    candidate,
    `${candidate}.ts`,
    `${candidate}.tsx`,
    `${candidate}.vue`,
    `${candidate}/index.ts`,
    `${candidate}/index.tsx`,
  ]) {
    const resolved = modulePaths.get(path)
    if (resolved) {
      return resolved
    }
  }
  return null
}

const violations = []
const dependencyGraph = new Map()
const typeScriptSources = parseTypeScriptSources(sourceFiles)
const typeScriptSourcesByOwner = new Map()
for (const entry of typeScriptSources) {
  const owner = normalizedPath(entry.ownerPath)
  typeScriptSourcesByOwner.set(owner, [...(typeScriptSourcesByOwner.get(owner) ?? []), entry])
}
for (const path of sourceFiles) {
  const owner = relative(sourceRoot, path).replaceAll('\\', '/')
  const imports = collectModuleSpecifiers(typeScriptSourcesByOwner.get(normalizedPath(path)) ?? [])
  const internalDependencies = imports
    .map((dependency) => resolveInternalImport(path, dependency))
    .filter((dependency) => dependency !== null)
  dependencyGraph.set(owner, new Set(internalDependencies))

}

const appConfig = ts.readConfigFile(resolve(process.cwd(), 'tsconfig.app.json'), ts.sys.readFile)
if (appConfig.error) {
  throw new Error(ts.flattenDiagnosticMessageText(appConfig.error.messageText, '\n'))
}
const parsedAppConfig = ts.parseJsonConfigFileContent(appConfig.config, ts.sys, process.cwd())
const productionTypeScriptPaths = typeScriptSources.map(({ path }) => path)
const ownerPaths = new Map(typeScriptSources.map(({ path, ownerPath }) => [normalizedPath(path), ownerPath]))
const productionProgram = createTypeScriptProgram(typeScriptSources, parsedAppConfig.options)
const templateSources = new Map(
  sourceFiles
    .filter((path) => extname(path) === '.vue')
    .map((path) => [normalizedPath(path), compileVueTemplate(path, readFileSync(path, 'utf8'))]),
)
for (const { path, interfaceName, name } of collectUnusedPortMembers(
  productionProgram,
  productionTypeScriptPaths,
  ownerPaths,
)) {
  const owner = relative(process.cwd(), path).replaceAll('\\', '/')
  violations.push(
    `frontend port member has no production consumer: ${owner} -> ${interfaceName}.${name}`,
  )
}

for (const { ownerPath, factoryName, memberName } of collectUnusedReturnedMembers(
  productionProgram,
  productionTypeScriptPaths,
  ownerPaths,
  templateSources,
)) {
  const owner = relative(process.cwd(), ownerPath).replaceAll('\\', '/')
  violations.push(
    `frontend returned member has no production consumer: ${owner} -> ${factoryName}.${memberName}`,
  )
}

for (const { path, alias, generated } of collectGeneratedMirrorAliases(
  productionProgram,
  productionTypeScriptPaths,
  ownerPaths,
)) {
  const owner = relative(process.cwd(), path).replaceAll('\\', '/')
  violations.push(
    `frontend type alias mirrors generated contract type: ${owner} -> ${alias} = ${generated}`,
  )
}

const states = new Map()
const stack = []
const cycles = new Set()

function visit(modulePath) {
  states.set(modulePath, 'visiting')
  stack.push(modulePath)
  for (const dependency of dependencyGraph.get(modulePath) ?? []) {
    if (!states.has(dependency)) {
      visit(dependency)
      continue
    }
    if (states.get(dependency) !== 'visiting') {
      continue
    }
    const members = stack.slice(stack.indexOf(dependency))
    const rotations = members.map((_, index) => [...members.slice(index), ...members.slice(0, index)])
    rotations.sort((left, right) => left.join('\0').localeCompare(right.join('\0')))
    const canonical = rotations[0]
    cycles.add([...canonical, canonical[0]].join(' -> '))
  }
  stack.pop()
  states.set(modulePath, 'visited')
}

for (const modulePath of dependencyGraph.keys()) {
  if (!states.has(modulePath)) {
    visit(modulePath)
  }
}
for (const cycle of [...cycles].sort()) {
  violations.push(`frontend dependency cycle: ${cycle}`)
}

for (const path of walk(e2eRoot)) {
  const source = readFileSync(path, 'utf8')
  const sourceFile = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true)
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) {
      continue
    }
    if (!statement.moduleSpecifier.text.startsWith('@/')) {
      continue
    }
    const clause = statement.importClause
    const namedImports = clause?.namedBindings && ts.isNamedImports(clause.namedBindings)
      ? clause.namedBindings.elements
      : []
    const isTypeOnly = clause?.isTypeOnly === true
      || (
        clause?.name === undefined
        && namedImports.length > 0
        && namedImports.every((element) => element.isTypeOnly)
      )
    if (!isTypeOnly) {
      const owner = relative(process.cwd(), path).replaceAll('\\', '/')
      violations.push(
        `E2E runtime import must be relative because WDIO does not resolve @ aliases: ${owner} -> ${statement.moduleSpecifier.text}`,
      )
    }
  }
}

const unreachableModules = collectUnreachableModules(
  dependencyGraph,
  ['main.ts'],
  new Set(Object.keys(AMBIENT_SOURCE_ALLOWLIST)),
)
for (const modulePath of unreachableModules) {
  violations.push(`frontend production source is unreachable from src/main.ts: ${modulePath}`)
}

const allowlists = [
  ['ambient source', AMBIENT_SOURCE_ALLOWLIST],
  ['generated source', GENERATED_SOURCE_ALLOWLIST],
  ['Knip dependency', KNIP_DEPENDENCY_ALLOWLIST],
]
for (const [kind, entries] of allowlists) {
  for (const [name, entry] of Object.entries(entries)) {
    if (!entry.reason.trim()) {
      violations.push(`${kind} allowlist entry has no reason: ${name}`)
    }
    const evidencePath = resolve(process.cwd(), entry.evidenceFile)
    let evidence
    try {
      evidence = readFileSync(evidencePath, 'utf8')
    } catch {
      violations.push(`${kind} allowlist evidence file is missing: ${name} -> ${entry.evidenceFile}`)
      continue
    }
    if (!evidence.includes(entry.marker)) {
      violations.push(`${kind} allowlist evidence marker is missing: ${name} -> ${entry.marker}`)
    }
  }
}

for (const name of Object.keys(AMBIENT_SOURCE_ALLOWLIST)) {
  if (!name.endsWith('.d.ts')) {
    violations.push(`ambient source allowlist entry is not a declaration file: ${name}`)
  }
}

if (violations.length > 0) {
  process.stderr.write(`${violations.join('\n')}\n`)
  process.exitCode = 1
} else {
  process.stdout.write('Frontend dependency graph is acyclic\n')
}

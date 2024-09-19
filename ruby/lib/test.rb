#!/usr/bin/env ruby
require 'json'
require 'uri'
require 'pathname'
require_relative 'stduritemplate'

template_file = ARGV[0]
data_file = ARGV[1]

begin
  data = JSON.parse(File.read(data_file))
rescue Errno::ENOENT
  $stderr.puts("File '#{data_file}' not found.")
  exit(1)
rescue JSON::ParserError => e
  $stderr.puts("Error parsing JSON data: #{e.message}")
  exit(1)
end

begin
  template = File.read(template_file).strip
rescue Errno::ENOENT
  $stderr.puts("File '#{template_file}' not found.")
  exit(1)
end

begin
  result = StdUriTemplate.expand(template, data)
  puts result
rescue StandardError => e
  $stderr.puts("Error expanding template: #{e.message}")
  $stderr.puts(e.backtrace.join("\n"))
  puts 'false'
end

// Source: data/benchmarks/sv-benchmarks/loops/while_infinite_loop_1.c

void loopy_468(void) {
  int x=0;

  while(1)
  {
    {;
//@ assert(x==0);
}
    
  }

  {;
//@ assert(x!=0);
}

}
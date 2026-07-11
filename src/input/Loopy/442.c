// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/loopv3.c
extern int unknown_int(void);

int SIZE = 50000001;

void loopy_442(void) {
  int i, j;
  i = 0; j=0;
  while(i<SIZE){ 

    if(unknown_int())	  
      i = i + 8; 
    else
     i = i + 4;    
	  
  }
  j = i/4 ;
    {;
//@ assert( (j * 4) == i);
}

  return;
}